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

import logging
from twisted.web.resource import Resource
import phonenumbers

from sydent.validators.msisdnvalidator import SessionExpiredException
from sydent.validators.msisdnvalidator import IncorrectClientSecretException

from sydent.http.servlets import require_args, jsonwrap, send_cors


logger = logging.getLogger(__name__)


class MsisdnRequestCodeServlet(Resource):
    isLeaf = True

    def __init__(self, syd):
        self.sydent = syd

    @jsonwrap
    def render_POST(self, request):
        send_cors(request)

        error = require_args(request, ('phone_number', 'country', 'client_secret', 'send_attempt'))
        if error:
            request.setResponseCode(400)
            return error

        raw_phone_number = request.args['phone_number'][0]
        country = request.args['country'][0]
        clientSecret = request.args['client_secret'][0]
        sendAttempt = request.args['send_attempt'][0]

        try:
            phone_number_object = phonenumbers.parse(raw_phone_number, country)
        except Exception as e:
            logger.warn("Invalid phone number given: %r", e)
            request.setResponseCode(400)
            return {'errcode': 'M_INVALID_PHONE_NUMBER', 'error': "Invalid phone number" }

        msisdn = phonenumbers.format_number(
            phone_number_object, phonenumbers.PhoneNumberFormat.E164
        )[1:]

        resp = None

        try:
            sid = self.sydent.validators.msisdn.requestToken(
                msisdn, clientSecret, sendAttempt, None
            )
        except e:
            logger.error("Exception sending SMS: %r", e);
            request.setResponseCode(500)
            resp = {'errcode': 'M_UNKNOWN', 'error':'Internal Server Error'}

        if not resp:
            resp = {'success': True, 'sid': sid}

        return resp

    @jsonwrap
    def render_OPTIONS(self, request):
        send_cors(request)
        request.setResponseCode(200)
        return {}


class MsisdnValidateCodeServlet(Resource):
    isLeaf = True

    def __init__(self, syd):
        self.sydent = syd

    def render_GET(self, request):
        resp = self.do_validate_request(request)
        if 'success' in resp and resp['success']:
            msg = "Verification successful! Please return to your Matrix client to continue."
            if 'nextLink' in request.args:
                next_link = request.args['nextLink'][0]
                request.setResponseCode(302)
                request.setHeader("Location", next_link)
        else:
            msg = "Verification failed: you may need to request another verification text"

        templateFile = self.sydent.cfg.get('http', 'verify_response_template')

        request.setHeader("Content-Type", "text/html")
        return open(templateFile).read() % {'message': msg}

    @jsonwrap
    def render_POST(self, request):
        return self.do_validate_request(request)

    def do_validate_request(self, request):
        send_cors(request)

        err = require_args(request, ('token', 'sid', 'client_secret'))
        if err:
            return err

        sid = request.args['sid'][0]
        tokenString = request.args['token'][0]
        clientSecret = request.args['client_secret'][0]

        try:
            resp = self.sydent.validators.msisdn.validateSessionWithToken(sid, clientSecret, tokenString)
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
