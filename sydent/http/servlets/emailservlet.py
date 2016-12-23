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

from sydent.util.emailutils import EmailAddressException, EmailSendException
from sydent.validators.emailvalidator import SessionExpiredException
from sydent.validators.emailvalidator import IncorrectClientSecretException

from sydent.http.servlets import get_args, jsonwrap, send_cors


class EmailRequestCodeServlet(Resource):
    isLeaf = True

    def __init__(self, syd):
        self.sydent = syd

    @jsonwrap
    def render_POST(self, request):
        send_cors(request)

        error, args = get_args(request, ('email', 'client_secret', 'send_attempt'))
        if error:
            request.setResponseCode(400)
            return error

        email = args['email']
        clientSecret = args['client_secret']
        sendAttempt = args['send_attempt']

        ipaddress = self.sydent.ip_from_request(request)

        nextLink = None
        if 'next_link' in args and not args['next_link'].startswith("file:///"):
            nextLink = args['next_link']

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
            resp = {'success': True, 'sid': str(sid)}

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
        if 'success' in resp and resp['success']:
            msg = "Verification successful! Please return to your Matrix client to continue."
            if 'nextLink' in request.args:
                next_link = request.args['nextLink'][0]
                if not next_link.startswith("file:///"):
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

        err, args = get_args(request, ('token', 'sid', 'client_secret'))
        if err:
            return err

        sid = args['sid']
        tokenString = args['token']
        clientSecret = args['client_secret']

        try:
            resp = self.sydent.validators.email.validateSessionWithToken(sid, clientSecret, tokenString)
        except IncorrectClientSecretException:
            return {'success': False, 'errcode': 'M_INCORRECT_CLIENT_SECRET',
                    'error': "Client secret does not match the one given when requesting the token"}
        except SessionExpiredException:
            return {'success': False, 'errcode': 'M_SESSION_EXPIRED',
                    'error': "This validation session has expired: call requestToken again"}

        if not resp:
            resp = {'success': False}

        return resp

    @jsonwrap
    def render_OPTIONS(self, request):
        send_cors(request)
        request.setResponseCode(200)
        return {}
