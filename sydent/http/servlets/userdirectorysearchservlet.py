# -*- coding: utf-8 -*-

# Copyright 2018 New Vector Ltd
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
from twisted.internet import defer
from twisted.web import server
from signedjson.sign import SignatureVerifyException

import logging
import json

from sydent.http.servlets import deferjsonwrap, jsonwrap, send_cors
from sydent.db.profiles import ProfileStore


logger = logging.getLogger(__name__)

MAX_SEARCH_LIMIT = 100


class UserDirectorySearchServlet(Resource):
    isLeaf = True

    def __init__(self, syd):
        self.sydent = syd

    def render_POST(self, request):
        self._async_render_POST(request)
        return server.NOT_DONE_YET

    @deferjsonwrap
    @defer.inlineCallbacks
    def _async_render_POST(self, request):
        send_cors(request)
        try:
            content = request.content.read()
            if isinstance(content, bytes):
                content = content.decode("UTF-8")

            body = json.loads(content)
        except ValueError:
            request.setResponseCode(400)
            defer.returnValue({'errcode': 'M_BAD_JSON', 'error': 'Malformed JSON'})

        if 'search_term' not in body:
            request.setResponseCode(400)
            defer.returnValue({'errcode': 'M_MISSING_PARAMS', 'error': 'Missing param: search_term'})

        search_term = body['search_term']
        limit = min(body.get('limit', 10), MAX_SEARCH_LIMIT)

        try:
            yield self.sydent.sig_verifier.verifyServerSignedJson(body, self.sydent.user_dir_allowed_hses)
        except SignatureVerifyException:
            request.setResponseCode(403)
            msg = "Signature verification failed or origin not whitelisted"
            defer.returnValue({'errcode': 'M_FORBIDDEN', 'error': msg})

        profileStore = ProfileStore(self.sydent)

        # search for one more result than the limit: if we get limit + 1, we know there
        # are more results we could have returned
        results = profileStore.getProfilesMatchingSearchTerm(search_term, limit + 1)

        defer.returnValue({'results': results[0:limit], 'limited': len(results) > limit})

    @jsonwrap
    def render_OPTIONS(self, request):
        send_cors(request)
        request.setResponseCode(200)
        return {}
