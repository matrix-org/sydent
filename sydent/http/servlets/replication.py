# -*- coding: utf-8 -*-

# Copyright 2014 OpenMarket Ltd
# Copyright 2019 New Vector Ltd
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
from __future__ import absolute_import

from twisted.web.resource import Resource
from twisted.web import server
from twisted.internet import defer
from sydent.http.servlets import jsonwrap, MatrixRestError
from sydent.threepid import threePidAssocFromDict

from sydent.util.hash import sha256_and_url_safe_base64

from sydent.db.hashing_metadata import HashingMetadataStore
from sydent.db.peers import PeerStore
from sydent.db.threepid_associations import GlobalAssociationStore
from sydent.db.invite_tokens import JoinTokenStore
from sydent.http.servlets import deferjsonwrap
from sydent.replication.peer import NoMatchingSignatureException, NoSignaturesException, RemotePeerError
from signedjson.sign import SignatureVerifyException

import logging
import json

logger = logging.getLogger(__name__)


class ReplicationPushServlet(Resource):
    def __init__(self, sydent):
        self.sydent = sydent
        self.hashing_store = HashingMetadataStore(sydent)

    def render_POST(self, request):
        self._async_render_POST(request)
        return server.NOT_DONE_YET

    @deferjsonwrap
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
            raise MatrixRestError(403, 'M_UNKNOWN_PEER', 'This peer is not known to this server')

        logger.info("Push connection made from peer %s", peer.servername)

        if not request.requestHeaders.hasHeader('Content-Type') or \
                request.requestHeaders.getRawHeaders('Content-Type')[0] != 'application/json':
            logger.warn("Peer %s made push connection with non-JSON content (type: %s)",
                        peer.servername, request.requestHeaders.getRawHeaders('Content-Type')[0])
            raise MatrixRestError(400, 'M_NOT_JSON', 'This endpoint expects JSON')

        try:
            # json.loads doesn't allow bytes in Python 3.5
            inJson = json.loads(request.content.read().decode("UTF-8"))
        except ValueError:
            logger.warn("Peer %s made push connection with malformed JSON", peer.servername)
            raise MatrixRestError(400, 'M_BAD_JSON', 'Malformed JSON')

        # Ensure there is data we are able to process
        if 'sg_assocs' not in inJson and 'invite_tokens' not in inJson and 'ephemeral_public_keys' not in inJson:
            logger.warn("Peer %s made push connection with no 'sg_assocs', 'invite_tokens' or 'ephemeral_public_keys' keys in JSON", peer.servername)
            raise MatrixRestError(400, 'M_BAD_JSON', 'No "sg_assocs", "invite_tokens" or "ephemeral_public_keys" key in JSON')

        # Process signed associations
        #
        # They come in roughly this structure:
        # {
        #   "sg_assocs": {
        #     {
        #       # The key is the origin id value
        #       "1": {
        #         ... association information ...
        #       },
        #       ...
        #     }
        #   }
        # }

        # Ensure items are pulled out of the dictionary in order of origin_id.
        sg_assocs = inJson.get('sg_assocs', {})
        sg_assocs = sorted(
            sg_assocs.items(), key=lambda k: int(k[0])
        )

        globalAssocsStore = GlobalAssociationStore(self.sydent)

        # Check that this message is signed by one of our trusted associated peers
        for originId, sgAssoc in sg_assocs:
            try:
                yield peer.verifySignedAssociation(sgAssoc)
                logger.debug("Signed association from %s with origin ID %s verified", peer.servername, originId)
            except (NoSignaturesException, NoMatchingSignatureException, RemotePeerError, SignatureVerifyException):
                self.sydent.db.rollback()
                logger.warn("Failed to verify signed association from %s with origin ID %s", peer.servername, originId)
                raise MatrixRestError(400, 'M_VERIFICATION_FAILED', 'Signature verification failed')
            except Exception:
                self.sydent.db.rollback()
                logger.error("Failed to verify signed association from %s with origin ID %s", peer.servername, originId)
                raise MatrixRestError(500, 'M_INTERNAL_SERVER_ERROR', 'Signature verification failed')

            assocObj = threePidAssocFromDict(sgAssoc)

            if assocObj.mxid is not None:
                # Calculate the lookup hash with our own pepper for this association
                str_to_hash = ' '.join(
                    [assocObj.address, assocObj.medium,
                     self.hashing_store.get_lookup_pepper()],
                )
                assocObj.lookup_hash = sha256_and_url_safe_base64(str_to_hash)

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

        # Process any new invite tokens
        #
        # They come in roughly this structure:
        # {
        #   "added": {
        #     {
        #       # The key is the origin id value
        #       "1": {
        #         ... invite token information ...
        #       },
        #       ...
        #     }
        #   }
        # }

        # Get the container dictionary of new and updated invites
        invite_tokens = inJson.get('invite_tokens', {})

        # Extract the dictionary of new invites
        new_invites = invite_tokens.get('added', {})

        # Convert to an ordered list to ensure we process invites in order.
        #
        # Otherwise we have a risk of ignoring certain updates due to our behaviour of
        # ignoring old updates that may've been accidentally sent twice
        new_invites = sorted(
            new_invites.items(), key=lambda k: int(k[0])
        )

        for originId, inviteToken in new_invites:
            tokensStore.storeToken(inviteToken['medium'], inviteToken['address'], inviteToken['room_id'],
                                inviteToken['sender'], inviteToken['token'],
                                originServer=peer.servername, originId=originId,
                                commit=False)
            logger.info("Stored invite token with origin ID %s from %s", originId, peer.servername)

        # Process any invite token update
        #
        # They come in roughly this structure:
        # {
        #   # Note `updated` is a list here instead of a dictionary
        #   "updated": [
        #     {
        #       "origin_id": 1,
        #       ... invite token information ...
        #     },
        #     ...
        #   ]
        # }

        # Updated invite tokens come as a list of dictionaries rather than a
        # dictionary of dictionaries
        #
        # Extract them from invite_tokens first
        invite_updates = invite_tokens.get('updated', [])

        # Then extract the list of invite token update dictionaries, ensuring
        # tokens are processed in order of origin_id
        invite_updates = sorted(
            invite_updates, key=lambda k: int(k["origin_id"])
        )

        for updated_invite in invite_updates:
            tokensStore.updateToken(updated_invite['medium'], updated_invite['address'], updated_invite['room_id'],
                                updated_invite['sender'], updated_invite['token'], updated_invite['sent_ts'],
                                origin_server=updated_invite['origin_server'], origin_id=updated_invite['origin_id'],
                                is_deletion=updated_invite.get('is_deletion', False), commit=False)
            logger.info("Stored invite update with origin ID %s from %s", updated_invite['origin_id'], peer.servername)

        # Process any ephemeral public keys
        #
        # They come in roughly this structure:
        # {
        #   "ephemeral_public_keys": {
        #     "1": {
        #       ... public key information ...
        #     },
        #     ...
        #   }
        # }

        ephemeral_public_keys = inJson.get("ephemeral_public_keys", {})
        ephemeral_public_keys = sorted(
            ephemeral_public_keys.items(), key=lambda k: int(k[0])
        )

        for originId, ephemeralKey in ephemeral_public_keys:
            tokensStore.storeEphemeralPublicKey(
                ephemeralKey['public_key'], persistenceTs=ephemeralKey['persistence_ts'],
                originServer=peer.servername, originId=originId, commit=False)
            logger.info("Stored ephemeral key with origin ID %s from %s", originId, peer.servername)

        self.sydent.db.commit()
        defer.returnValue({'success': True})
