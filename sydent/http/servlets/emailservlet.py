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

from sydent.validators.emailvalidator import EmailAddressException, EmailSendException, SessionExpiredException
from sydent.validators.emailvalidator import IncorrectClientSecretException

from sydent.http.servlets import require_args, jsonwrap

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

    @jsonwrap
    def render_POST(self, request):
        send_cors(request)

        error = require_args(request, ('email', 'clientSecret', 'sendAttempt'))
        if error:
            return error

        email = request.args['email'][0]
        clientSecret = request.args['clientSecret'][0]
        sendAttempt = request.args['sendAttempt'][0]

        resp = None

        try:
            tokenId = self.sydent.validators.email.requestToken(email, clientSecret, sendAttempt)
        except EmailAddressException:
            request.setResponseCode(400)
            resp = {'error': 'email_invalid'}
        except EmailSendException:
            request.setResponseCode(500)
            resp = {'error': 'send_error'}

        if not resp:
            resp = {'success':True, 'tokenId':tokenId}

        return resp

    @jsonwrap
    def render_OPTIONS(self, request):
        send_cors(request)
        request.setResponseCode(200)
        return {}

class EmailValidateCodeServlet(Resource):
    isLeaf = True

    def __init__(self, syd):
        self.sydent = syd

    @jsonwrap
    def render_POST(self, request):
        send_cors(request)

        err = require_args(request, ('token', 'tokenId', 'clientSecret'))
        if err:
            return err

        tokenId = request.args['tokenId'][0]
        tokenString = request.args['token'][0]
        clientSecret = request.args['clientSecret'][0]

        try:
            sgassoc = self.sydent.validators.email.validateSessionWithToken(tokenId, clientSecret, tokenString)
        except IncorrectClientSecretException:
            return {'error': 'incorrect-client-secret',
                    'message': "Client secret does not match the one given when requesting the token"}
        except SessionExpiredException:
            return {'error': 'session-expired',
                    'message': "This validation session has expired: call requestToken again"}

        if not sgassoc:
            sgassoc = {'success':False}

        return sgassoc

    @jsonwrap
    def render_OPTIONS(self, request):
        send_cors(request)
        request.setResponseCode(200)
        return {}
