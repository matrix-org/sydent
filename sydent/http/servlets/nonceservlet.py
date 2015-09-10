# -*- coding: utf-8 -*-

# Copyright 2015 OpenMarket Ltd
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
import hashlib
import random
import string

from twisted.web.resource import Resource

import json
from sydent.db.invite_tokens import JoinTokenStore
from sydent.db.threepid_associations import GlobalAssociationStore

from sydent.http.servlets import require_args, send_cors


class NonceServlet(Resource):
    def __init__(self, syd):
        self.sydent = syd

    def render_POST(self, request):
        send_cors(request)
        err = require_args(request, ("medium", "address", "room_id",))
        if err:
            return json.dumps(err)
        medium = request.args["medium"][0]
        address = request.args["address"][0]
        roomId = request.args["room_id"][0]

        globalAssocStore = GlobalAssociationStore(self.sydent)
        mxid = globalAssocStore.getMxid(medium, address)
        if mxid:
            request.setResponseCode(400)
            return json.dumps({
                "errcode": "THREEPID_IN_USE",
                "error": "Binding already known",
                "mxid": mxid,
            })

        outerNonce = self._randomString(256)
        innerNonce = self._randomString(256)
        innerDigest = hashlib.sha256(innerNonce + medium + address).hexdigest()
        outerDigest = hashlib.sha256(outerNonce + innerDigest).hexdigest()

        JoinTokenStore(self.sydent).storeToken(medium, address, roomId, innerNonce)

        resp = {
            "nonce": outerNonce,
            "digest": outerDigest,
        }

        return json.dumps(resp)

    def _randomString(self, length):
        return ''.join(random.choice(string.ascii_letters) for _ in xrange(length))
