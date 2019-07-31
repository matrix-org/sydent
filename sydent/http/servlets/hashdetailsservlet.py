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
from sydent.db.threepid_associations import GlobalAssociationStore
from sydent.util.tokenutils import generateAlphanumericTokenOfLength

import logging
import json
import signedjson.sign

from sydent.http.servlets import get_args, jsonwrap, send_cors


logger = logging.getLogger(__name__)


class HashDetailsServlet(Resource):
    isLeaf = True

    def __init__(self, syd):
        self.sydent = syd
        self.known_algorithms = ["sha256", "none"]

    def render_GET(self, request):
        """
        Return the hashing algorithms and pepper that this IS supports.
        Whether the response includes the "none" algorithm is determined by a
        config option. The pepper included in the response is also set by the
        config, and generated if one is not set.

        Returns: An object containing an array of hashing algorithms the
                 server supports, and a `lookup_pepper` field, which is a
                 server-defined value that the client should include in the 3PID
                 information before hashing.
        """
        send_cors(request)

        # Determine what hashing algorithms have been enabled
        algorithms = self.sydent.config.get("hashing", "algorithms")
        if not algorithms:
            # Default response
            algorithms = ["sha256"]

        # A lookup_pepper is defined in the config, otherwise it is generated 
        lookup_pepper = self.sydent.config.get("hashing", "lookup_pepper")
        
        return {
            "algorithms": algorithms,
            "lookup_pepper": lookup_pepper,
        }

    @jsonwrap
    def render_OPTIONS(self, request):
        send_cors(request)
        request.setResponseCode(200)
        return {}
