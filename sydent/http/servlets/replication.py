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

from sydent.util.hash import sha256_and_url_safe_base64

from sydent.db.hashing_metadata import HashingMetadataStore
from sydent.db.peers import PeerStore
from sydent.db.threepid_associations import GlobalAssociationStore

import logging
import json

logger = logging.getLogger(__name__)

class ReplicationPushServlet(Resource):
    def __init__(self, sydent):
        self.sydent = sydent
        self.hashing_store = HashingMetadataStore(sydent)

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

        if 'sgAssocs' not in inJson:
            logger.warn("Peer %s made push connection with no 'sgAssocs' key in JSON", peer.servername)
            return {'errcode': 'M_BAD_JSON', 'error': 'No "sgAssocs" key in JSON'}

        failedIds = []

        globalAssocsStore = GlobalAssociationStore(self.sydent)

        for originId, sgAssoc in inJson['sgAssocs'].items():
            try:
                peer.verifySignedAssociation(sgAssoc)
                logger.debug("Signed association from %s with origin ID %s verified", peer.servername, originId)

                # Don't bother adding if one has already failed: we add all of them or none so
                # we're only going to roll back the transaction anyway (but we continue to try
                # & verify the rest so we can give a complete list of the ones that don't
                # verify)
                if len(failedIds) > 0:
                    continue

                assocObj = threePidAssocFromDict(sgAssoc)

                if assocObj.mxid is not None:
                    # Calculate the lookup hash with our own pepper for this association
                    str_to_hash = ' '.join(
                        [assocObj.address, assocObj.medium,
                         self.hashing_store.get_lookup_pepper()],
                    )
                    assocObj.lookup_hash = sha256_and_url_safe_base64(str_to_hash)

                    # Add this association
                    globalAssocsStore.addAssociation(
                        assocObj, json.dumps(sgAssoc), peer.servername, originId, commit=False
                    )
                else:
                    logger.info("Incoming deletion: removing associations for %s / %s", assocObj.medium, assocObj.address)
                    globalAssocsStore.removeAssociation(assocObj.medium, assocObj.address)
                logger.info("Stored association origin ID %s from %s", originId, peer.servername)
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
        else:
            self.sydent.db.commit()
            return {'success': True}
