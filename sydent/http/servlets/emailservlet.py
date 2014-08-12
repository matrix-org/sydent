# -*- coding: utf-8 -*-

# Copyright 2014 matrix.org
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

from sydent.validators.emailvalidator import EmailAddressException, EmailSendException

import json


def send_cors(request):
    request.setHeader(b"Content-Type", b"application/json")
    request.setHeader("Access-Control-Allow-Origin", "*")
    request.setHeader("Access-Control-Allow-Methods",
                      "GET, POST, PUT, DELETE, OPTIONS")
    request.setHeader("Access-Control-Allow-Headers",
                      "Origin, X-Requested-With, Content-Type, Accept")


class EmailRequestCodeServlet(Resource):
    isLeaf = True

    def __init__(self, syd):
        self.sydent = syd

    def render_POST(self, request):
        send_cors(request)
        if 'email' not in request.args or 'clientSecret' not in request.args:
            request.setResponseCode(400)
            resp = {'error': 'badrequest', 'message': "'email' and 'clientSecret' fields are required"}
            return json.dumps(resp)

        email = request.args['email'][0]
        clientSecret = request.args['clientSecret'][0]

        resp = None

        try:
            tokenId = self.sydent.validators.email.requestToken(email, clientSecret)
        except EmailAddressException:
            request.setResponseCode(400)
            resp = {'error': 'email_invalid'}
        except EmailSendException:
            request.setResponseCode(500)
            resp = {'error': 'send_error'}

        if not resp:
            resp = {'success':True, 'tokenId':tokenId}

        return json.dumps(resp).encode("UTF-8")

    def render_OPTIONS(self, request):
        send_cors(request)
        request.setResponseCode(200)
        return "{}".encode("UTF-8")

class EmailValidateCodeServlet(Resource):
    isLeaf = True

    def __init__(self, syd):
        self.sydent = syd

    def render_POST(self, request):
        send_cors(request)
        if 'tokenId' not in request.args or 'token' not in request.args or 'mxId' not in request.args:
            request.setResponseCode(400)
            resp = {'error': 'badrequest', 'message': "'tokenId', 'token' and 'mxId' fields are required"}
            return json.dumps(resp)

        tokenId = request.args['tokenId'][0]
        tokenString = request.args['token'][0]
        mxId = request.args['mxId'][0]

        sgassoc = self.sydent.validators.email.validateToken(tokenId, None, tokenString, mxId)

        if not sgassoc:
            sgassoc = {'success':False}

        return json.dumps(sgassoc).encode("UTF-8")

    def render_OPTIONS(self, request):
        send_cors(request)
        request.setResponseCode(200)
        return "{}".encode("UTF-8")
