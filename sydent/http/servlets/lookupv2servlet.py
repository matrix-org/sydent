# -*- coding: utf-8 -*-

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

from twisted.web.resource import Resource

import logging
import json
import signedjson.sign

from sydent.http.servlets import get_args, jsonwrap, send_cors
from sydent.db.threepid_associations import GlobalAssociationStore
from sydent.util.hash import parse_space_separated_str

logger = logging.getLogger(__name__)


class LookupV2Servlet(Resource):
    isLeaf = True

    def __init__(self, syd):
        self.sydent = syd
        self.globalAssociationStore = GlobalAssociationStore(self.sydent)

    def render_POST(self, request):
        """
        Perform lookups with potentially hashed 3PID details.

        Depending on our response to /hash_details, the client will chosoe a
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
        err, args = get_args(request, ('addresses', 'algorithm', 'pepper'))
        if err:
            return json.dumps(err)

        addresses = args['addresses']
        if not isinstance(addresses, list):
            request.setResponseCode(400)
            return {'errcode': 'M_INVALID_PARAM', 'error': 'addresses must be a list'}, None

        algorithm = args['algorithm']
        if not isinstance(algorithm, str):
            request.setResponseCode(400)
            return {'errcode': 'M_INVALID_PARAM', 'error': 'algorithm must be a string'}, None
        if algorithm not in self.sydent.config.get("hashing", "algorithms"):
            request.setResponseCode(400)
            return {'errcode': 'M_INVALID_PARAM', 'error': 'algorithm is not supported'}, None

        pepper = args['pepper']
        if not isinstance(pepper, str):
            request.setResponseCode(400)
            return {'errcode': 'M_INVALID_PARAM', 'error': 'pepper must be a string'}, None
        if pepper != self.sydent.config.get("hashing", "lookup_pepper"):
            request.setResponseCode(400)
            return {'errcode': 'M_INVALID_PEPPER', 'error': "pepper does not match server's"}, None

        logger.info("Lookup of %d threepids with algorithm", len(addresses), algorithm)
        if algorithm == "none":
            # Lookup without hashing
            medium_address_tuples = []
            for medium_and_address in addresses:
                # Parse medium, address components
                medium, address = parse_space_separated_str(medium_and_address)
                medium_address_tuples.append((medium, address))

            # Lookup the mxids
            medium_address_mxid_tuples = GlobalAssociationStore.getMxids(medium_address_tuples)

            return json.dumps({'mappings': {x[0]: x[2] for x in medium_address_mxid_tuples}})

        elif algorithm == "sha256":
            # Lookup using SHA256 with URL-safe base64 encoding
            mappings = {}
            for h in addresses:
                mxid = self.globalAssociationStore.retrieveMxidFromHash(h)
                if mxid:
                    mappings[h] = mxid

            return json.dumps({'mappings': mappings})

        return {'errcode': 'M_INVALID_PARAM', 'error': 'algorithm is not supported'}, None

    @jsonwrap
    def render_OPTIONS(self, request):
        send_cors(request)
        request.setResponseCode(200)
        return {}
