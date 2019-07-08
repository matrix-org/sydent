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
import nacl.signing
import random
import string
from email.header import Header

from six import string_types
from twisted.web.resource import Resource
from unpaddedbase64 import encode_base64

import json
from sydent.db.invite_tokens import JoinTokenStore
from sydent.db.threepid_associations import GlobalAssociationStore

from sydent.http.servlets import get_args, send_cors
from sydent.util.emailutils import sendEmail


class StoreInviteServlet(Resource):
    def __init__(self, syd):
        self.sydent = syd
        self.random = random.SystemRandom()

    def render_POST(self, request):
        send_cors(request)
        err, args = get_args(request, ("medium", "address", "room_id", "sender",))
        if err:
            return json.dumps(err)
        medium = args["medium"]
        address = args["address"]
        roomId = args["room_id"]
        sender = args["sender"]

        globalAssocStore = GlobalAssociationStore(self.sydent)
        mxid = globalAssocStore.getMxid(medium, address)
        if mxid:
            request.setResponseCode(400)
            return json.dumps({
                "errcode": "THREEPID_IN_USE",
                "error": "Binding already known",
                "mxid": mxid,
            })

        if medium != "email":
            request.setResponseCode(400)
            return json.dumps({
                "errcode": "M_UNRECOGNIZED",
                "error": "Didn't understand medium '%s'" % (medium,),
            })

        token = self._randomString(128)

        tokenStore = JoinTokenStore(self.sydent)

        ephemeralPrivateKey = nacl.signing.SigningKey.generate()
        ephemeralPublicKey = ephemeralPrivateKey.verify_key

        ephemeralPrivateKeyBase64 = encode_base64(ephemeralPrivateKey.encode(), True)
        ephemeralPublicKeyBase64 = encode_base64(ephemeralPublicKey.encode(), True)

        tokenStore.storeEphemeralPublicKey(ephemeralPublicKeyBase64)
        tokenStore.storeToken(medium, address, roomId, sender, token)

        substitutions = {}
        for k, v in args.items():
            if isinstance(v, string_types):
                substitutions[k] = v
        substitutions["token"] = token

        required = [
            'sender_display_name',
            'token',
            'room_name',
            'bracketed_room_name',
            'room_avatar_url',
            'sender_display_name',
            'guest_user_id',
            'guest_access_token',
        ]
        for k in required:
            substitutions.setdefault(k, '')

        substitutions["ephemeral_private_key"] = ephemeralPrivateKeyBase64
        if substitutions["room_name"] != '':
            substitutions["bracketed_room_name"] = "(%s)" % substitutions["room_name"]

        subject_header = Header(self.sydent.cfg.get('email', 'email.invite.subject', raw=True) % substitutions, 'utf8')
        substitutions["subject_header_value"] = subject_header.encode()

        sendEmail(self.sydent, "email.invite_template", address, substitutions)

        pubKey = self.sydent.keyring.ed25519.verify_key
        pubKeyBase64 = encode_base64(pubKey.encode())

        baseUrl = "%s/_matrix/identity/api/v1" % (self.sydent.cfg.get('http', 'client_http_base'),)

        keysToReturn = []
        keysToReturn.append({
            "public_key": pubKeyBase64,
            "key_validity_url": baseUrl + "/pubkey/isvalid",
        })
        keysToReturn.append({
            "public_key": ephemeralPublicKeyBase64,
            "key_validity_url": baseUrl + "/pubkey/ephemeral/isvalid",
        })

        resp = {
            "token": token,
            "public_key": pubKeyBase64,
            "public_keys": keysToReturn,
            "display_name": self.redact(address),
        }

        return json.dumps(resp)

    def redact(self, address):
        return "@".join(map(self._redact, address.split("@", 1)))

    def _redact(self, s):
        if len(s) > 5:
            return s[:3] + "..."
        elif len(s) > 1:
            return s[0] + "..."
        else:
            return "..."

    def _randomString(self, length):
        return ''.join(self.random.choice(string.ascii_letters) for _ in xrange(length))
