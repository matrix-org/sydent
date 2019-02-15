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
from sydent.http.servlets import jsonwrap
from sydent.threepid import threePidAssocFromDict
from sydent.db.peers import PeerStore
from sydent.db.threepid_associations import GlobalAssociationStore
from sydent.db.invite_tokens import JoinTokenStore

import logging
import json

logger = logging.getLogger(__name__)

class ReplicationPushServlet(Resource):
    def __init__(self, sydent):
        self.sydent = sydent

    @jsonwrap
    def render_POST(self, request):
        peerCert = request.transport.getPeerCertificate()
        peerCertCn = peerCert.get_subject().commonName

        peerStore = PeerStore(self.sydent)

        peer = peerStore.getPeerByName(peerCertCn)

        if not peer:
            logger.warn("Got connection from %s but no peer found by that name", peerCertCn)
            request.setResponseCode(403)
            return {'errcode': 'M_UNKNOWN_PEER', 'error': 'This peer is not known to this server'}

        logger.info("Push connection made from peer %s", peer.servername)

        if not request.requestHeaders.hasHeader('Content-Type') or \
                request.requestHeaders.getRawHeaders('Content-Type')[0] != 'application/json':
            logger.warn("Peer %s made push connection with non-JSON content (type: %s)",
                        peer.servername, request.requestHeaders.getRawHeaders('Content-Type')[0])
            return {'errcode': 'M_NOT_JSON', 'error': 'This endpoint expects JSON'}

        try:
            inJson = json.load(request.content)
        except ValueError:
            logger.warn("Peer %s made push connection with malformed JSON", peer.servername)
            return {'errcode': 'M_BAD_JSON', 'error': 'Malformed JSON'}

        if 'sg_assocs' not in inJson and 'invite_tokens' not in inJson and 'ephemeral_keys' not in inJson:
            logger.warn("Peer %s made push connection with no 'sg_assocs', 'invite_tokens' or 'ephemeral_keys' keys in JSON", peer.servername)
            return {'errcode': 'M_BAD_JSON', 'error': 'No "sg_assocs", "invite_tokens" or "ephemeral_keys" key in JSON'}

        if 'sg_assocs' in inJson:
            failedIds = []

            globalAssocsStore = GlobalAssociationStore(self.sydent)

            # Check that this message is signed by one of our trusted associated peers
            for originId, sgAssoc in inJson['sg_assocs'].items():
                try:
                    peer.verifyMessage(sgAssoc)
                    logger.debug("Signed association from %s with origin ID %s verified", peer.servername, originId)

                    # Don't bother adding if one has already failed: we add all of them or none so we're only going to
                    # roll back the transaction anyway (but we continue to try & verify the rest so we can give a
                    # complete list of the ones that don't verify)
                    if len(failedIds) > 0:
                        continue

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

                except:
                    failedIds.append(originId)
                    logger.warn("Failed to verify signed association from %s with origin ID %s",
                                peer.servername, originId)
                    twisted.python.log.err()

            if len(failedIds) > 0:
                self.sydent.db.rollback()
                request.setResponseCode(400)
                return {'errcode': 'M_VERIFICATION_FAILED', 'error': 'Verification failed for one or more associations',
                        'failed_ids':failedIds}

        if 'invite_tokens' in inJson or 'ephemeral_keys' in inJson:
            tokensStore = JoinTokenStore(self.sydent)

            # TODO: Peer verification (kinda important lest someone just sends something to this endpoint!!)
            # TODO: Ensure they aren't going over 100 tokens/keys
                # Have some sort of verify function in peer/invite_tokens?

            if 'invite_tokens' in inJson and len(inJson['invite_tokens']) > 0:
                last_processed_id = tokensStore.getLastTokensIdFromServer(peer.servername)
                for originId, inviteToken in inJson["invite_tokens"].items():
                    # Make sure we haven't processed this token already
                    # If so, back out of all incoming tokens and return an error
                    if originId >= last_processed_id:
                        self.sydent.db.rollback()
                        request.setResponseCode(200)
                        return {'success': True, 'message': 'Already processed key ID %s' % str(originId)}

                    tokensStore.storeToken(inviteToken['medium'], inviteToken['address'], inviteToken['room_id'],
                                        inviteToken['sender'], inviteToken['token'],
                                        originServer=peer.servername, originId=originId, commit=False)
                    logger.info("Stored invite token with origin ID %s from %s", originId, peer.servername)

            if 'ephemeral_keys' in inJson and len(inJson['ephemeral_keys']) > 0:
                last_processed_id = tokensStore.getLastEphemeralKeysIdFromServer(peer.servername)
                for originId, ephemeralKey in inJson["ephemeral_keys"].items():
                    # Make sure we haven't processed this token already
                    # If so, back out of all incoming tokens and return an error
                    if originId >= last_processed_id:
                        self.sydent.db.rollback()
                        request.setResponseCode(200)
                        return {'success': True, 'message': 'Already processed key ID %s' % str(originId)}

                    tokensStore.storeEphemeralPublicKey(
                        ephemeralKey['public_key'], persistenceTs=ephemeralKey['persistence_ts'],
                        originServer=peer.servername, originId=originId, commit=False)
                    logger.info("Stored ephemeral key with origin ID %s from %s", originId, peer.servername)


        self.sydent.db.commit()
        return {'success':True}
