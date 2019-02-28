# -*- coding: utf-8 -*-

# Copyright 2014 OpenMarket Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import twisted.python.log
from twisted.web.resource import Resource
from twisted.web import server
from twisted.internet import defer
from sydent.http.servlets import jsonwrap
from sydent.threepid import threePidAssocFromDict
from sydent.db.peers import PeerStore
from sydent.db.threepid_associations import GlobalAssociationStore
from sydent.db.invite_tokens import JoinTokenStore
from sydent.replication.peer import NoMatchingSignatureException, NoSignaturesException, RemotePeerError
from signedjson.sign import SignatureVerifyException

import logging
import json

logger = logging.getLogger(__name__)

MAX_SG_ASSOCS_LIMIT = 100
MAX_INVITE_TOKENS_LIMIT = 100
MAX_EPHEMERAL_PUBLIC_KEYS_LIMIT = 100

class ReplicationPushServlet(Resource):
    def __init__(self, sydent):
        self.sydent = sydent

    def render_POST(self, request):
        self._async_render_POST(request)
        return server.NOT_DONE_YET

    @defer.inlineCallbacks
    def _async_render_POST(self, request):
        """Verify and store replicated information from trusted peer identity servers.

        To prevent data sent from erroneous servers from being stored, we
        initially verify that the sender's certificate contains a commonName
        that we trust. This is checked against the peers stored in the local
        DB. Data is then ingested.

        Replicated associations must each be individually signed by the
        signing key of the remote peer, which we verify using the verifykey
        stored in the local DB.

        Other data does not need to be signed.

        :params request: The HTTPS request.
        """

        peerCert = request.transport.getPeerCertificate()
        peerCertCn = peerCert.get_subject().commonName

        peerStore = PeerStore(self.sydent)

        peer = peerStore.getPeerByName(peerCertCn)

        if not peer:
            logger.warn("Got connection from %s but no peer found by that name", peerCertCn)
            request.setResponseCode(403)
            request.write(json.dumps({'errcode': 'M_UNKNOWN_PEER', 'error': 'This peer is not known to this server'}))
            request.finish()
            return

        logger.info("Push connection made from peer %s", peer.servername)

        if not request.requestHeaders.hasHeader('Content-Type') or \
                request.requestHeaders.getRawHeaders('Content-Type')[0] != 'application/json':
            logger.warn("Peer %s made push connection with non-JSON content (type: %s)",
                        peer.servername, request.requestHeaders.getRawHeaders('Content-Type')[0])
            request.setResponseCode(400)
            request.write(json.dumps({'errcode': 'M_NOT_JSON', 'error': 'This endpoint expects JSON'}))
            request.finish()
            return

        try:
            inJson = json.load(request.content)
        except ValueError:
            logger.warn("Peer %s made push connection with malformed JSON", peer.servername)
            request.setResponseCode(400)
            request.write(json.dumps({'errcode': 'M_BAD_JSON', 'error': 'Malformed JSON'}))
            request.finish()
            return

        # Ensure there is data we are able to process
        if 'sg_assocs' not in inJson and 'invite_tokens' not in inJson and 'ephemeral_public_keys' not in inJson:
            logger.warn("Peer %s made push connection with no 'sg_assocs', 'invite_tokens' or 'ephemeral_public_keys' keys in JSON", peer.servername)
            request.setResponseCode(400)
            request.write(json.dumps({'errcode': 'M_BAD_JSON', 'error': 'No "sg_assocs", "invite_tokens" or "ephemeral_public_keys" key in JSON'}))
            request.finish()
            return

        # Process signed associations
        sg_assocs = inJson.get('sg_assocs', {})
        if len(sg_assocs) > MAX_SG_ASSOCS_LIMIT:
            logger.warn("Peer %s made push with 'sg_assocs' field containing %d entries, which is greater than the maximum %d", peer.servername, len(sg_assocs), MAX_SG_ASSOCS_LIMIT)
            request.setResponseCode(400)
            request.write(json.dumps({'errcode': 'M_BAD_JSON', 'error': '"sg_assocs" has more than %d keys' % MAX_SG_ASSOCS_LIMIT}))
            request.finish()
            return

        globalAssocsStore = GlobalAssociationStore(self.sydent)

        # Check that this message is signed by one of our trusted associated peers
        for originId, sgAssoc in sg_assocs.items():
            try:
                yield peer.verifySignedAssociation(sgAssoc)
                logger.debug("Signed association from %s with origin ID %s verified", peer.servername, originId)
            except (NoSignaturesException, NoMatchingSignatureException, RemotePeerError, SignatureVerifyException):
                self.sydent.db.rollback()
                logger.warn("Failed to verify signed association from %s with origin ID %s", peer.servername, originId)
                request.setResponseCode(400)
                request.write(json.dumps({'errcode': 'M_VERIFICATION_FAILED', 'error': 'Signature verification failed'}))
                request.finish()
                return
            except Exception:
                self.sydent.db.rollback()
                logger.error("Failed to verify signed association from %s with origin ID %s", peer.servername, originId)
                request.setResponseCode(500)
                request.write(json.dumps({'errcode': 'M_INTERNAL_SERVER_ERROR', 'error': 'Signature verification failed'}))
                request.finish()
                return

            assocObj = threePidAssocFromDict(sgAssoc)

            if assocObj.mxid is not None:
                # Add the association components and the original signed
                # object (as assocs must be signed when requested by clients)
                globalAssocsStore.addAssociation(assocObj, json.dumps(sgAssoc), peer.servername, originId, commit=False)
            else:
                logger.info("Incoming deletion: removing associations for %s / %s", assocObj.medium, assocObj.address)
                globalAssocsStore.removeAssociation(assocObj.medium, assocObj.address)

            logger.info("Stored association with origin ID %s from %s", originId, peer.servername)

            # if this is an association that matches one of our invite_tokens then we should call the onBind callback
            # at this point, in order to tell the inviting HS that someone out there has just bound the 3PID.
            self.sydent.threepidBinder.notifyPendingInvites(assocObj)

        tokensStore = JoinTokenStore(self.sydent)

        # Process any invite tokens

        invite_tokens = inJson.get('invite_tokens', {})
        if len(invite_tokens) > MAX_INVITE_TOKENS_LIMIT:
            self.sydent.db.rollback()
            logger.warn("Peer %s made push with 'sg_assocs' field containing %d entries, which is greater than the maximum %d", peer.servername, len(invite_tokens), MAX_INVITE_TOKENS_LIMIT)
            request.setResponseCode(400)
            request.write(json.dumps({'errcode': 'M_BAD_JSON', 'error': '"invite_tokens" has more than %d keys' % MAX_INVITE_TOKENS_LIMIT}))
            request.finish()
            return

        for originId, inviteToken in invite_tokens.items():
            tokensStore.storeToken(inviteToken['medium'], inviteToken['address'], inviteToken['room_id'],
                                inviteToken['sender'], inviteToken['token'],
                                originServer=peer.servername, originId=originId, commit=False)
            logger.info("Stored invite token with origin ID %s from %s", originId, peer.servername)

        # Process any ephemeral public keys

        ephemeral_public_keys = inJson.get('ephemeral_public_keys', {})
        if len(ephemeral_public_keys) > MAX_EPHEMERAL_PUBLIC_KEYS_LIMIT:
            self.sydent.db.rollback()
            logger.warn("Peer %s made push with 'sg_assocs' field containing %d entries, which is greater than the maximum %d", peer.servername, len(ephemeral_public_keys), MAX_EPHEMERAL_PUBLIC_KEYS_LIMIT)
            request.setResponseCode(400)
            request.write(json.dumps({'errcode': 'M_BAD_JSON', 'error': '"ephemeral_public_keys" has more than %d keys' % MAX_EPHEMERAL_PUBLIC_KEYS_LIMIT}))
            request.finish()
            return

        for originId, ephemeralKey in ephemeral_public_keys.items():
            tokensStore.storeEphemeralPublicKey(
                ephemeralKey['public_key'], persistenceTs=ephemeralKey['persistence_ts'],
                originServer=peer.servername, originId=originId, commit=False)
            logger.info("Stored ephemeral key with origin ID %s from %s", originId, peer.servername)

        self.sydent.db.commit()
        request.write(json.dumps({'success':True}))
        request.finish()
        return
