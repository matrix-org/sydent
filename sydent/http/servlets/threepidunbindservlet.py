# -*- coding: utf-8 -*-

# Copyright 2014 OpenMarket Ltd
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

import json

from twisted.web.resource import Resource
from twisted.web import server
from twisted.internet import defer

from sydent.http.servlets import get_args, jsonwrap
from sydent.hs_federation.verifier import NoAuthenticationError
from signedjson.sign import SignatureVerifyException

class ThreePidUnbindServlet(Resource):
    def __init__(self, sydent):
        self.sydent = sydent

    def render_POST(self, request):
        self._async_render_POST(request)
        return server.NOT_DONE_YET

    @defer.inlineCallbacks
    def _async_render_POST(self, request):
        try:
            body = json.load(request.content)
        except ValueError:
            request.setResponseCode(400)
            request.write(json.dumps({'errcode': 'M_BAD_JSON', 'error': 'Malformed JSON'}))
            request.finish()
            return

        missing = [k for k in ("threepid", "mxid") if k not in body]
        if len(missing) > 0:
            request.setResponseCode(400)
            msg = "Missing parameters: "+(",".join(missing))
            request.write(json.dumps({'errcode': 'M_MISSING_PARAMS', 'error': msg}))
            request.finish()
            return

        threepid = body['threepid']
        mxid = body['mxid']

        if 'medium' not in threepid or 'address' not in threepid:
            request.setResponseCode(400)
            request.write(json.dumps({'errcode': 'M_MISSING_PARAMS', 'error': 'Threepid lacks medium / address'}))
            request.finish()
            return

        try:
            origin_server_name = yield self.sydent.sig_verifier.authenticate_request(request, body)
        except SignatureVerifyException as ex:
            request.setResponseCode(401)
            request.write(json.dumps({'errcode': 'M_FORBIDDEN', 'error': ex.message}))
            request.finish()
            return
        except NoAuthenticationError as ex:
            request.setResponseCode(401)
            request.write(json.dumps({'errcode': 'M_FORBIDDEN', 'error': ex.message}))
            request.finish()
            return

        if not mxid.endswith(':' + origin_server_name):
            request.setResponseCode(403)
            request.write(json.dumps({'errcode': 'M_FORBIDDEN', 'error': 'Origin server name does not match mxid'}))
            request.finish()

        res = self.sydent.threepidBinder.removeBinding(threepid, mxid)
        request.write(json.dumps({}))
        request.finish()
