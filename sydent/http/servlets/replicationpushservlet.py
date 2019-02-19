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

        #peerCert = request.transport.getPeerCertificate()
        #peerCertCn = peerCert.get_subject().commonName

        peerStore = PeerStore(self.sydent)

        peerCertCn = "localhost"
        peer = peerStore.getPeerByName(peerCertCn)

        if not peer:
            logger.exception("Got connection from %s but no peer found by that name", peerCertCn)
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

        if 'sg_assocs' not in inJson and 'invite_tokens' not in inJson and 'ephemeral_public_keys' not in inJson:
            logger.warn("Peer %s made push connection with no 'sg_assocs', 'invite_tokens' or 'ephemeral_public_keys' keys in JSON", peer.servername)
            request.setResponseCode(400)
            request.write(json.dumps({'errcode': 'M_BAD_JSON', 'error': 'No "sg_assocs", "invite_tokens" or "ephemeral_public_keys" key in JSON'}))
            request.finish()
            return

        # Verify signature of message JSON
        try:
            logger.debug("VERIFYING")
            yield peer.verifyMessage(inJson)
            logger.debug("Signed replication JSON from %s verified", peer.servername)
        except (NoSignaturesException, NoMatchingSignatureException, RemotePeerError, SignatureVerifyException):
            logger.warn("Failed to verify JSON from %s", peer.servername)
            request.setResponseCode(400)
            request.write(json.dumps({'errcode': 'M_VERIFICATION_FAILED', 'error': 'Signature verification failed'}))
            request.finish()
            return
        except Exception:
            logger.exception("Failed to verify JSON from %s", peer.servername)
            request.setResponseCode(500)
            request.write(json.dumps({'errcode': 'M_INTERNAL_SERVER_ERROR', 'error': 'Signature verification failed'}))
            request.finish()
            return

        if 'sg_assocs' in inJson and len(inJson['sg_assocs']) > 0:
            if len(inJson['sg_assocs']) > MAX_SG_ASSOCS_LIMIT:
                request.setResponseCode(400)
                request.write(json.dumps({'errcode': 'M_BAD_JSON', 'error': '"sg_assocs" has more than %d keys' % MAX_SG_ASSOCS_LIMIT}))
                request.finish()
                return

            globalAssocsStore = GlobalAssociationStore(self.sydent)

            # Check that this message is signed by one of our trusted associated peers
            for originId, sgAssoc in inJson['sg_assocs'].items():
                assocObj = threePidAssocFromDict(sgAssoc)

                if assocObj.mxid is not None:
                    globalAssocsStore.addAssociation(assocObj, json.dumps(sgAssoc), peer.servername, originId, commit=False)
                else:
                    logger.info("Incoming deletion: removing associations for %s / %s", assocObj.medium, assocObj.address)
                    globalAssocsStore.removeAssociation(assocObj.medium, assocObj.address)
                logger.info("Stored association with origin ID %s from %s", originId, peer.servername)

                # if this is an association that matches one of our invite_tokens then we should call the onBind callback
                # at this point, in order to tell the inviting HS that someone out there has just bound the 3PID.
                self.sydent.threepidBinder.notifyPendingInvites(assocObj)

        if 'invite_tokens' in inJson or 'ephemeral_public_keys' in inJson:
            tokensStore = JoinTokenStore(self.sydent)

            if 'invite_tokens' in inJson and len(inJson['invite_tokens']) > 0:
                if len(inJson['invite_tokens']) > MAX_INVITE_TOKENS_LIMIT:
                    self.sydent.db.rollback()
                    request.setResponseCode(400)
                    request.write(json.dumps({'errcode': 'M_BAD_JSON', 'error': '"invite_tokens" has more than %d keys' % MAX_INVITE_TOKENS_LIMIT}))
                    request.finish()
                    return

                last_processed_id = tokensStore.getLastTokensIdFromServer(peer.servername)
                for originId, inviteToken in inJson["invite_tokens"].items():
                    # Make sure we haven't processed this token already
                    # If so, back out of all incoming tokens and return an error
                    if int(originId) <= int(last_processed_id):
                        self.sydent.db.rollback()
                        request.setResponseCode(200)
                        request.write(json.dumps({'success': True, 'message': 'Already processed token ID %s' % str(originId)}))
                        request.finish()
                        return

                    tokensStore.storeToken(inviteToken['medium'], inviteToken['address'], inviteToken['room_id'],
                                        inviteToken['sender'], inviteToken['token'],
                                        originServer=peer.servername, originId=originId, commit=False)
                    logger.info("Stored invite token with origin ID %s from %s", originId, peer.servername)

            if 'ephemeral_public_keys' in inJson and len(inJson['ephemeral_public_keys']) > 0:
                if len(inJson['ephemeral_public_keys']) > MAX_EPHEMERAL_PUBLIC_KEYS_LIMIT:
                    self.sydent.db.rollback()
                    request.setResponseCode(400)
                    request.write(json.dumps({'errcode': 'M_BAD_JSON', 'error': '"ephemeral_public_keys" has more than %d keys' % MAX_EPHEMERAL_PUBLIC_KEYS_LIMIT}))
                    request.finish()
                    return

                last_processed_id = tokensStore.getLastEphemeralKeysIdFromServer(peer.servername)
                for originId, ephemeralKey in inJson["ephemeral_public_keys"].items():
                    # Make sure we haven't processed this key already
                    # If so, back out of all incoming keys and return an error
                    if int(originId) <= int(last_processed_id):
                        self.sydent.db.rollback()
                        request.setResponseCode(200)
                        request.write(json.dumps({'success': True, 'message': 'Already processed key ID %s' % str(originId)}))
                        request.finish()
                        return

                    tokensStore.storeEphemeralPublicKey(
                        ephemeralKey['public_key'], persistenceTs=ephemeralKey['persistence_ts'],
                        originServer=peer.servername, originId=originId, commit=False)
                    logger.info("Stored ephemeral key with origin ID %s from %s", originId, peer.servername)

        self.sydent.db.commit()
        request.write(json.dumps({'success':True}))
        request.finish()
        return
