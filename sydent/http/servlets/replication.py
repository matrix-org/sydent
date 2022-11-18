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

import json
import logging
from typing import TYPE_CHECKING, List, cast

import twisted.python.log
from OpenSSL.crypto import X509
from twisted.internet.interfaces import ISSLTransport
from twisted.web.server import Request

from sydent.db.hashing_metadata import HashingMetadataStore
from sydent.db.peers import PeerStore
from sydent.db.threepid_associations import GlobalAssociationStore, SignedAssociations
from sydent.http.servlets import MatrixRestError, SydentResource, jsonwrap
from sydent.threepid import threePidAssocFromDict
from sydent.types import JsonDict
from sydent.util import json_decoder
from sydent.util.hash import sha256_and_url_safe_base64
from sydent.util.stringutils import normalise_address

if TYPE_CHECKING:
    from sydent.sydent import Sydent

logger = logging.getLogger(__name__)


class ReplicationPushServlet(SydentResource):
    def __init__(self, sydent: "Sydent") -> None:
        super().__init__()
        self.sydent = sydent
        self.hashing_store = HashingMetadataStore(sydent)

    @jsonwrap
    def render_POST(self, request: Request) -> JsonDict:
        # Cast safety: This request has an ISSLTransport because this servlet
        # is a resource under the ReplicationHttpsServer and nowhere else.
        request.transport = cast(ISSLTransport, request.transport)
        peerCert = cast(X509, request.transport.getPeerCertificate())
        peerCertCn = peerCert.get_subject().commonName

        peerStore = PeerStore(self.sydent)

        peer = peerStore.getPeerByName(peerCertCn)

        if not peer:
            logger.warning(
                "Got connection from %s but no peer found by that name", peerCertCn
            )
            raise MatrixRestError(
                403, "M_UNKNOWN_PEER", "This peer is not known to this server"
            )

        logger.info("Push connection made from peer %s", peer.servername)

        if (
            not request.requestHeaders.hasHeader("Content-Type")
            # Type safety: the hasHeader call returned True, so getRawHeaders()
            # returns a nonempty list.
            or request.requestHeaders.getRawHeaders("Content-Type")[0]  # type: ignore[index]
            != "application/json"
        ):
            logger.warning(
                "Peer %s made push connection with non-JSON content (type: %s)",
                peer.servername,
                # Type safety: the hasHeader call returned True, so getRawHeaders()
                # returns a nonempty list.
                request.requestHeaders.getRawHeaders("Content-Type")[0],  # type: ignore[index]
            )
            raise MatrixRestError(400, "M_NOT_JSON", "This endpoint expects JSON")

        try:
            # json.loads doesn't allow bytes in Python 3.5
            inJson = json_decoder.decode(request.content.read().decode("UTF-8"))
        except ValueError:
            logger.warning(
                "Peer %s made push connection with malformed JSON", peer.servername
            )
            raise MatrixRestError(400, "M_BAD_JSON", "Malformed JSON")

        if "sgAssocs" not in inJson:
            logger.warning(
                "Peer %s made push connection with no 'sgAssocs' key in JSON",
                peer.servername,
            )
            raise MatrixRestError(400, "M_BAD_JSON", 'No "sgAssocs" key in JSON')

        failedIds: List[int] = []

        globalAssocsStore = GlobalAssociationStore(self.sydent)

        # Ensure items are pulled out of the dictionary in order of origin_id.
        sg_assocs_raw: SignedAssociations = inJson.get("sgAssocs", {})
        sg_assocs = sorted(sg_assocs_raw.items(), key=lambda k: int(k[0]))

        for originId, sgAssoc in sg_assocs:
            try:
                peer.verifySignedAssociation(sgAssoc)
                logger.debug(
                    "Signed association from %s with origin ID %s verified",
                    peer.servername,
                    originId,
                )

                # Don't bother adding if one has already failed: we add all of them or none so
                # we're only going to roll back the transaction anyway (but we continue to try
                # & verify the rest so we can give a complete list of the ones that don't
                # verify)
                if len(failedIds) > 0:
                    continue

                assocObj = threePidAssocFromDict(sgAssoc)

                # ensure we are casefolding email addresses before hashing/storing
                assocObj.address = normalise_address(assocObj.address, assocObj.medium)

                if assocObj.mxid is not None:
                    # Calculate the lookup hash with our own pepper for this association
                    pepper = self.hashing_store.get_lookup_pepper()
                    assert pepper is not None
                    str_to_hash = " ".join(
                        [assocObj.address, assocObj.medium, pepper],
                    )
                    assocObj.lookup_hash = sha256_and_url_safe_base64(str_to_hash)

                    # Add this association
                    globalAssocsStore.addAssociation(
                        assocObj,
                        json.dumps(sgAssoc),
                        peer.servername,
                        originId,
                        commit=False,
                    )
                else:
                    logger.info(
                        "Incoming deletion: removing associations for %s / %s",
                        assocObj.medium,
                        assocObj.address,
                    )
                    globalAssocsStore.removeAssociation(
                        assocObj.medium, assocObj.address
                    )
                logger.info(
                    "Stored association origin ID %s from %s", originId, peer.servername
                )
            except Exception:
                failedIds.append(originId)
                logger.warning(
                    "Failed to verify signed association from %s with origin ID %s",
                    peer.servername,
                    originId,
                )
                twisted.python.log.err()

        if len(failedIds) > 0:
            self.sydent.db.rollback()
            request.setResponseCode(400)
            return {
                "errcode": "M_VERIFICATION_FAILED",
                "error": "Verification failed for one or more associations",
                "failed_ids": failedIds,
            }
        else:
            self.sydent.db.commit()
            return {"success": True}
