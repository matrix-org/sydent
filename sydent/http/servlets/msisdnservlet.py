# -*- coding: utf-8 -*-

# Copyright 2016 OpenMarket Ltd
# Copyright 2017 Vector Creations Ltd
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

from sydent.validators import (
    IncorrectClientSecretException, SessionExpiredException, DestinationRejectedException
)

from sydent.http.servlets import get_args, jsonwrap, send_cors
from sydent.http.auth import authIfV2


logger = logging.getLogger(__name__)


class MsisdnRequestCodeServlet(Resource):
    isLeaf = True

    def __init__(self, syd):
        self.sydent = syd

    @jsonwrap
    def render_POST(self, request):
        send_cors(request)

        authIfV2(self.sydent, request)

        args = get_args(request, ('phone_number', 'country', 'client_secret', 'send_attempt'))

        raw_phone_number = args['phone_number']
        country = args['country']
        clientSecret = args['client_secret']
        sendAttempt = args['send_attempt']

        try:
            phone_number_object = phonenumbers.parse(raw_phone_number, country)
        except Exception as e:
            logger.warn("Invalid phone number given: %r", e)
            request.setResponseCode(400)
            return {'errcode': 'M_INVALID_PHONE_NUMBER', 'error': "Invalid phone number" }

        msisdn = phonenumbers.format_number(
            phone_number_object, phonenumbers.PhoneNumberFormat.E164
        )[1:]

        # International formatted number. The same as an E164 but with spaces
        # in appropriate places to make it nicer for the humans.
        intl_fmt = phonenumbers.format_number(
            phone_number_object, phonenumbers.PhoneNumberFormat.INTERNATIONAL
        )

        resp = None

        try:
            sid = self.sydent.validators.msisdn.requestToken(
                phone_number_object, clientSecret, sendAttempt, None
            )
        except DestinationRejectedException:
            logger.error("Destination rejected for number: %s", msisdn);
            request.setResponseCode(400)
            resp = {'errcode': 'M_DESTINATION_REJECTED', 'error': 'Phone numbers in this country are not currently supported'}
        except Exception as e:
            logger.error("Exception sending SMS: %r", e);
            request.setResponseCode(500)
            resp = {'errcode': 'M_UNKNOWN', 'error':'Internal Server Error'}

        if not resp:
            resp = {
                'success': True, 'sid': str(sid),
                'msisdn': msisdn, 'intl_fmt': intl_fmt,
            }

        return resp

    def render_OPTIONS(self, request):
        send_cors(request)
        request.setResponseCode(200)
        return b''


class MsisdnValidateCodeServlet(Resource):
    isLeaf = True

    def __init__(self, syd):
        self.sydent = syd

    def render_GET(self, request):
        send_cors(request)

        err, args = get_args(request, ('token', 'sid', 'client_secret'))
        if err:
            msg = "Verification failed: Your request was invalid."
        else:
            resp = self.do_validate_request(args)
            if 'success' in resp and resp['success']:
                msg = "Verification successful! Please return to your Matrix client to continue."
                if 'next_link' in args:
                    next_link = args['next_link']
                    request.setResponseCode(302)
                    request.setHeader("Location", next_link)
            else:
                msg = "Verification failed: you may need to request another verification text"

        templateFile = self.sydent.cfg.get('http', 'verify_response_template')

        request.setHeader("Content-Type", "text/html")
        return open(templateFile).read() % {'message': msg}

    @jsonwrap
    def render_POST(self, request):
        send_cors(request)

        authIfV2(self.sydent, request)

        args = get_args(request, ('token', 'sid', 'client_secret'))

        return self.do_validate_request(args)

    def do_validate_request(self, args):
        sid = args['sid']
        tokenString = args['token']
        clientSecret = args['client_secret']

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

    def render_OPTIONS(self, request):
        send_cors(request)
        request.setResponseCode(200)
        return b''
