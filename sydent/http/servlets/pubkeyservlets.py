# -*- coding: utf-8 -*-

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
from __future__ import absolute_import

from twisted.web.resource import Resource
from unpaddedbase64 import encode_base64

from sydent.db.invite_tokens import JoinTokenStore
from sydent.http.servlets import get_args, jsonwrap


class Ed25519Servlet(Resource):
    isLeaf = True

    def __init__(self, syd):
        self.sydent = syd

    @jsonwrap
    def render_GET(self, request):
        pubKey = self.sydent.keyring.ed25519.verify_key
        pubKeyBase64 = encode_base64(pubKey.encode())

        return {'public_key': pubKeyBase64}

class PubkeyIsValidServlet(Resource):
    isLeaf = True

    def __init__(self, syd):
        self.sydent = syd

    @jsonwrap
    def render_GET(self, request):
        args = get_args(request, ("public_key",))

        pubKey = self.sydent.keyring.ed25519.verify_key
        pubKeyBase64 = encode_base64(pubKey.encode())

        return {'valid': args["public_key"] == pubKeyBase64}


class EphemeralPubkeyIsValidServlet(Resource):
    isLeaf = True

    def __init__(self, syd):
        self.joinTokenStore = JoinTokenStore(syd)

    @jsonwrap
    def render_GET(self, request):
        args = get_args(request, ("public_key",))
        publicKey = args["public_key"]

        return {
            'valid': self.joinTokenStore.validateEphemeralPublicKey(publicKey),
        }
