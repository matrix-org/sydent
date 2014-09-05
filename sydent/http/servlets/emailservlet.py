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

from twisted.web.resource import Resource

from sydent.validators.emailvalidator import EmailAddressException, EmailSendException, SessionExpiredException
from sydent.validators.emailvalidator import IncorrectClientSecretException

from sydent.http.servlets import require_args, jsonwrap, send_cors


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
            sid = self.sydent.validators.email.requestToken(email, clientSecret, sendAttempt)
        except EmailAddressException:
            request.setResponseCode(400)
            resp = {'errcode': 'M_INVALID_EMAIL', 'error':'Invalid email address'}
        except EmailSendException:
            request.setResponseCode(500)
            resp = {'errcode': 'M_EMAIL_SEND_ERROR', 'error': 'Failed to sent email'}

        if not resp:
            resp = {'success': True, 'sid': sid}

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

        err = require_args(request, ('token', 'sid', 'clientSecret'))
        if err:
            return err

        sid = request.args['sid'][0]
        tokenString = request.args['token'][0]
        clientSecret = request.args['clientSecret'][0]

        try:
            resp = self.sydent.validators.email.validateSessionWithToken(sid, clientSecret, tokenString)
        except IncorrectClientSecretException:
            return {'errcode': 'M_INCORRECT_CLIENT_SECRET',
                    'error': "Client secret does not match the one given when requesting the token"}
        except SessionExpiredException:
            return {'errcode': 'M_SESSION_EXPIRED',
                    'error': "This validation session has expired: call requestToken again"}

        if not resp:
            resp = {'success': False}

        return resp

    @jsonwrap
    def render_OPTIONS(self, request):
        send_cors(request)
        request.setResponseCode(200)
        return {}
