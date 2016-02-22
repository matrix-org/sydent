# -*- coding: utf-8 -*-

# Copyright 2016 OpenMarket Ltd
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

import json
import signedjson.key
import signedjson.sign
from sydent.db.invite_tokens import JoinTokenStore
from sydent.http.servlets import require_args


class BlindlySignStuffServlet(Resource):
    isLeaf = True

    def __init__(self, syd):
        self.server_name = syd.server_name
        self.tokenStore = JoinTokenStore(syd)

    def render_POST(self, request):

        err = require_args(request, ("private_key", "token", "mxid"))
        if err:
            return json.dumps(err)

        private_key_base64 = request.args['private_key'][0]
        token = request.args['token'][0]
        mxid = request.args['mxid'][0]

        sender = self.tokenStore.getSenderForToken(token)
        if sender is None:
            request.setResponseCode(404)
            return json.dumps({
                "errcode": "M_UNRECOGNIZED",
                "error": "Didn't recognized token",
            })

        to_sign = {
            "mxid": mxid,
            "sender": sender,
            "token": token,
        }
        try:
            private_key = signedjson.key.decode_signing_key_base64(
                "ed25519",
                "0",
                private_key_base64
            )
            signed = signedjson.sign.sign_json(
                to_sign,
                self.server_name,
                private_key
            )
        except:
            return json.dumps({
                "errcode": "M_UNKNOWN",
            })

        return json.dumps(signed)
