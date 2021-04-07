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
from __future__ import absolute_import

from twisted.web.resource import Resource
from twisted.internet import defer

import logging
import json
from six.moves import urllib

from sydent.http.servlets import get_args, jsonwrap, deferjsonwrap, send_cors
from sydent.http.httpclient import FederationHttpClient
from sydent.users.tokens import issueToken
from sydent.util.stringutils import is_valid_matrix_server_name

logger = logging.getLogger(__name__)


class RegisterServlet(Resource):
    isLeaf = True

    def __init__(self, syd):
        self.sydent = syd
        self.client = FederationHttpClient(self.sydent)

    @deferjsonwrap
    @defer.inlineCallbacks
    def render_POST(self, request):
        """
        Register with the Identity Server
        """
        send_cors(request)

        args = get_args(request, ('matrix_server_name', 'access_token'))

        matrix_server = args['matrix_server_name'].lower()

        if not is_valid_matrix_server_name(matrix_server):
            request.setResponseCode(400)
            return {
                'errcode': 'M_INVALID_PARAM',
                'error': 'matrix_server_name must be a valid Matrix server name (IP address or hostname)'
            }

        result = yield self.client.get_json(
            "matrix://%s/_matrix/federation/v1/openid/userinfo?access_token=%s"
            % (
                matrix_server,
                urllib.parse.quote(args['access_token']),
            ),
            1024 * 5,
        )

        if 'sub' not in result:
            raise Exception("Invalid response from homeserver")

        user_id = result['sub']

        if not isinstance(user_id, str):
            request.setResponseCode(500)
            return {
                'errcode': 'M_UNKNOWN',
                'error': 'The Matrix homeserver returned a malformed reply'
            }

        user_id_components = user_id.split(':', 1)

        # Ensure there's a localpart and domain in the returned user ID.
        if len(user_id_components) != 2:
            request.setResponseCode(500)
            return {
                'errcode': 'M_UNKNOWN',
                'error': 'The Matrix homeserver returned an invalid MXID'
            }

        user_id_server = user_id_components[1]

        if not is_valid_matrix_server_name(user_id_server):
            request.setResponseCode(500)
            return {
                'errcode': 'M_UNKNOWN',
                'error': 'The Matrix homeserver returned an invalid MXID'
            }

        if user_id_server != matrix_server:
            request.setResponseCode(500)
            return {
                'errcode': 'M_UNKNOWN',
                'error': 'The Matrix homeserver returned a MXID belonging to another homeserver'
            }

        tok = yield issueToken(self.sydent, user_id)

        # XXX: `token` is correct for the spec, but we released with `access_token`
        # for a substantial amount of time. Serve both to make spec-compliant clients
        # happy.
        defer.returnValue({
            "access_token": tok,
            "token": tok,
        })

    def render_OPTIONS(self, request):
        send_cors(request)
        return b''
