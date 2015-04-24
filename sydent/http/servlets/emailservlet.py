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

        # error = require_args(request, ('email', 'client_secret', 'send_attempt'))
        error = require_args(request, ('email',))
        if error:
            request.setResponseCode(400)
            return error

        # look for both camelcase and underscores for transition
        if 'client_secret' in request.args:
            clientSecret = request.args['client_secret'][0]
        elif 'clientSecret' in request.args:
            clientSecret = request.args['clientSecret'][0]
        else:
            request.setResponseCode(400)
            return {'errcode': 'M_MISSING_PARAM', 'error':'No client_secret'}

        if 'send_attempt' in request.args:
            sendAttempt = request.args['send_attempt'][0]
        elif 'sendAttempt' in request.args:
            sendAttempt = request.args['sendAttempt'][0]
        else:
            request.setResponseCode(400)
            return {'errcode': 'M_MISSING_PARAM', 'error':'No send_attempt'}

        email = request.args['email'][0]

        ipaddress = self.sydent.ip_from_request(request)

        nextLink = None
        if 'next_link' in request.args:
            nextLink = request.args['next_link'][0]

        resp = None

        try:
            sid = self.sydent.validators.email.requestToken(
                email, clientSecret, sendAttempt, nextLink, ipaddress=ipaddress
            )
        except EmailAddressException:
            request.setResponseCode(400)
            resp = {'errcode': 'M_INVALID_EMAIL', 'error':'Invalid email address'}
        except EmailSendException:
            request.setResponseCode(500)
            resp = {'errcode': 'M_EMAIL_SEND_ERROR', 'error': 'Failed to send email'}

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

    def render_GET(self, request):
        resp = self.do_validate_request(request)
        if resp['success']:
            msg = "Verification successful! Please return to your Matrix client to continue."
            if 'nextLink' in request.args:
                next_link = request.args['nextLink'][0]
                request.setResponseCode(302)
                request.setHeader("Location", next_link)
        else:
            msg = "Verification failed: you may need to request another verification email"

        templateFile = self.sydent.cfg.get('http', 'verify_response_template')

        request.setHeader("Content-Type", "text/html")
        return open(templateFile).read() % {'message': msg}

    @jsonwrap
    def render_POST(self, request):
        return self.do_validate_request(request)

    def do_validate_request(self, request):
        send_cors(request)

        # err = require_args(request, ('token', 'sid', 'client_secret'))
        err = require_args(request, ('token', 'sid'))
        if err:
            return err

        sid = request.args['sid'][0]
        tokenString = request.args['token'][0]
        if 'client_secret' in request.args:
            clientSecret = request.args['client_secret'][0]
        elif 'clientSecret' in request.args:
            clientSecret = request.args['clientSecret'][0]
        else:
            request.setResponseCode(400)
            return {'errcode': 'M_MISSING_PARAM', 'error':'No client_secret'}

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
