# Copyright 2019 The Matrix.org Foundation C.I.C.
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

import logging
from typing import TYPE_CHECKING

from twisted.web.server import Request

from sydent.db.threepid_associations import GlobalAssociationStore
from sydent.http.auth import authV2
from sydent.http.servlets import SydentResource, get_args, jsonwrap, send_cors
from sydent.http.servlets.hashdetailsservlet import HashDetailsServlet
from sydent.types import JsonDict

if TYPE_CHECKING:
    from sydent.sydent import Sydent

logger = logging.getLogger(__name__)


class LookupV2Servlet(SydentResource):
    isLeaf = True

    def __init__(self, syd: "Sydent", lookup_pepper: str) -> None:
        super().__init__()
        self.sydent = syd
        self.globalAssociationStore = GlobalAssociationStore(self.sydent)
        self.lookup_pepper = lookup_pepper

    @jsonwrap
    def render_POST(self, request: Request) -> JsonDict:
        """
        Perform lookups with potentially hashed 3PID details.

        Depending on our response to /hash_details, the client will choose a
        hash algorithm and pepper, hash the 3PIDs it wants to lookup, and
        send them to us, along with the algorithm and pepper it used.

        We first check this algorithm/pepper combo matches what we expect,
        then compare the 3PID details to what we have in the database.

        Params: A JSON object containing the following keys:
                * 'addresses': List of hashed/plaintext (depending on the
                               algorithm) 3PID addresses and mediums.
                * 'algorithm': The algorithm the client has used to process
                               the 3PIDs.
                * 'pepper': The pepper the client has attached to the 3PIDs.

        Returns: Object with key 'mappings', which is a dictionary of results
                 where each result is a key/value pair of what the client sent, and
                 the matching Matrix User ID that claims to own that 3PID.

                 User IDs for which no mapping is found are omitted.
        """
        send_cors(request)

        authV2(self.sydent, request)

        args = get_args(request, ("addresses", "algorithm", "pepper"))

        addresses = args["addresses"]
        if not isinstance(addresses, list):
            request.setResponseCode(400)
            return {"errcode": "M_INVALID_PARAM", "error": "addresses must be a list"}

        algorithm = str(args["algorithm"])
        if algorithm not in HashDetailsServlet.known_algorithms:
            request.setResponseCode(400)
            return {"errcode": "M_INVALID_PARAM", "error": "algorithm is not supported"}

        # Ensure address count is under the configured limit
        limit = self.sydent.config.general.address_lookup_limit
        if len(addresses) > limit:
            request.setResponseCode(400)
            return {
                "errcode": "M_TOO_LARGE",
                "error": "More than the maximum amount of " "addresses provided",
            }

        pepper = str(args["pepper"])
        if pepper != self.lookup_pepper:
            request.setResponseCode(400)
            return {
                "errcode": "M_INVALID_PEPPER",
                "error": "pepper does not match '%s'" % (self.lookup_pepper,),
                "algorithm": algorithm,
                "lookup_pepper": self.lookup_pepper,
            }

        logger.info(
            "Lookup of %d threepid(s) with algorithm %s", len(addresses), algorithm
        )
        if algorithm == "none":
            # Lookup without hashing
            medium_address_tuples = []
            for address_and_medium in addresses:
                # Parse medium, address components
                address_medium_split = address_and_medium.split()

                # Forbid addresses that contain a space
                if len(address_medium_split) != 2:
                    request.setResponseCode(400)
                    return {
                        "errcode": "M_UNKNOWN",
                        "error": 'Invalid "address medium" pair: "%s"'
                        % address_and_medium,
                    }

                # Get the mxid for the address/medium combo if known
                address, medium = address_medium_split
                medium_address_tuples.append((medium, address))

            # Lookup the mxids
            medium_address_mxid_tuples = self.globalAssociationStore.getMxids(
                medium_address_tuples
            )

            # Return a dictionary of lookup_string: mxid values
            return {
                "mappings": {
                    "%s %s" % (x[1], x[0]): x[2] for x in medium_address_mxid_tuples
                }
            }

        elif algorithm == "sha256":
            # Lookup using SHA256 with URL-safe base64 encoding
            mappings = self.globalAssociationStore.retrieveMxidsForHashes(addresses)

            return {"mappings": mappings}

        request.setResponseCode(400)
        return {"errcode": "M_INVALID_PARAM", "error": "algorithm is not supported"}

    def render_OPTIONS(self, request: Request) -> bytes:
        send_cors(request)
        return b""
