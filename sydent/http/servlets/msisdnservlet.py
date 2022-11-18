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
from typing import TYPE_CHECKING

import phonenumbers
from twisted.web.server import Request

from sydent.http.auth import authV2
from sydent.http.servlets import (
    SydentResource,
    asyncjsonwrap,
    get_args,
    jsonwrap,
    send_cors,
)
from sydent.types import JsonDict
from sydent.util.ratelimiter import Ratelimiter
from sydent.util.stringutils import is_valid_client_secret
from sydent.validators import (
    DestinationRejectedException,
    IncorrectClientSecretException,
    IncorrectSessionTokenException,
    InvalidSessionIdException,
    SessionExpiredException,
)

if TYPE_CHECKING:
    from sydent.sydent import Sydent

logger = logging.getLogger(__name__)


class MsisdnRequestCodeServlet(SydentResource):
    isLeaf = True

    def __init__(self, syd: "Sydent", require_auth: bool = False) -> None:
        super().__init__()
        self.sydent = syd
        self.require_auth = require_auth
        self._msisdn_ratelimiter = Ratelimiter[str](
            syd.reactor,
            syd.config.sms.msisdn_ratelimit_burst,
            syd.config.sms.msisdn_ratelimit_rate_hz,
        )
        self._country_ratelimiter = Ratelimiter[int](
            syd.reactor,
            syd.config.sms.country_ratelimit_burst,
            syd.config.sms.country_ratelimit_rate_hz,
        )

    @asyncjsonwrap
    async def render_POST(self, request: Request) -> JsonDict:
        send_cors(request)

        if self.require_auth:
            authV2(self.sydent, request)

        args = get_args(
            request, ("phone_number", "country", "client_secret", "send_attempt")
        )

        raw_phone_number = args["phone_number"]
        country = args["country"]
        try:
            # See the comment handling `send_attempt` in emailservlet.py for
            # more context.
            sendAttempt = int(args["send_attempt"])
        except (TypeError, ValueError):
            request.setResponseCode(400)
            return {
                "errcode": "M_INVALID_PARAM",
                "error": f"send_attempt should be an integer (got {args['send_attempt']}",
            }
        clientSecret = args["client_secret"]

        if not is_valid_client_secret(clientSecret):
            request.setResponseCode(400)
            return {
                "errcode": "M_INVALID_PARAM",
                "error": "Invalid client_secret provided",
            }

        try:
            phone_number_object = phonenumbers.parse(raw_phone_number, country)

            if phone_number_object.country_code is None:
                raise Exception("No country code")
        except Exception as e:
            logger.warning("Invalid phone number given: %r", e)
            request.setResponseCode(400)
            return {
                "errcode": "M_INVALID_PHONE_NUMBER",
                "error": "Invalid phone number",
            }

        msisdn = phonenumbers.format_number(
            phone_number_object, phonenumbers.PhoneNumberFormat.E164
        )[1:]

        self._msisdn_ratelimiter.ratelimit(msisdn, "Limit exceeded for this number")
        self._country_ratelimiter.ratelimit(
            phone_number_object.country_code, "Limit exceeded for this country"
        )

        # International formatted number. The same as an E164 but with spaces
        # in appropriate places to make it nicer for the humans.
        intl_fmt = phonenumbers.format_number(
            phone_number_object, phonenumbers.PhoneNumberFormat.INTERNATIONAL
        )

        brand = self.sydent.brand_from_request(request)
        try:
            sid = await self.sydent.validators.msisdn.requestToken(
                phone_number_object, clientSecret, sendAttempt, brand
            )
            resp = {
                "success": True,
                "sid": str(sid),
                "msisdn": msisdn,
                "intl_fmt": intl_fmt,
            }
        except DestinationRejectedException:
            logger.warning("Destination rejected for number: %s", msisdn)
            request.setResponseCode(400)
            resp = {
                "errcode": "M_DESTINATION_REJECTED",
                "error": "Phone numbers in this country are not currently supported",
            }
        except Exception:
            logger.exception("Exception sending SMS")
            request.setResponseCode(500)
            resp = {"errcode": "M_UNKNOWN", "error": "Internal Server Error"}

        return resp

    def render_OPTIONS(self, request: Request) -> bytes:
        send_cors(request)
        return b""


class MsisdnValidateCodeServlet(SydentResource):
    isLeaf = True

    def __init__(self, syd: "Sydent", require_auth: bool = False) -> None:
        super().__init__()
        self.sydent = syd
        self.require_auth = require_auth

    def render_GET(self, request: Request) -> str:
        send_cors(request)

        args = get_args(request, ("token", "sid", "client_secret"))
        resp = self.do_validate_request(request)
        if "success" in resp and resp["success"]:
            msg = "Verification successful! Please return to your Matrix client to continue."
            if "next_link" in args:
                next_link = args["next_link"]
                request.setResponseCode(302)
                request.setHeader("Location", next_link)
        else:
            request.setResponseCode(400)
            msg = (
                "Verification failed: you may need to request another verification text"
            )

        brand = self.sydent.brand_from_request(request)

        # self.sydent.config.http.verify_response_template is deprecated
        if self.sydent.config.http.verify_response_template is None:
            templateFile = self.sydent.get_branded_template(
                brand,
                "verify_response_template.html",
            )
        else:
            templateFile = self.sydent.config.http.verify_response_template

        request.setHeader("Content-Type", "text/html")
        return open(templateFile).read() % {"message": msg}

    @jsonwrap
    def render_POST(self, request: Request) -> JsonDict:
        send_cors(request)

        if self.require_auth:
            authV2(self.sydent, request)

        return self.do_validate_request(request)

    def do_validate_request(self, request: Request) -> JsonDict:
        """
        Extracts information about a validation session from the request and
        attempts to validate that session.

        :param request: The request to extract information about the session from.

        :return: A dict with a "success" key which value indicates whether the
            validation succeeded. If the validation failed, this dict also includes
            a "errcode" and a "error" keys which include information about the failure.
        """

        args = get_args(request, ("token", "sid", "client_secret"))

        sid = args["sid"]
        tokenString = args["token"]
        clientSecret = args["client_secret"]

        if not is_valid_client_secret(clientSecret):
            request.setResponseCode(400)
            return {
                "errcode": "M_INVALID_PARAM",
                "error": "Invalid client_secret provided",
            }

        try:
            return self.sydent.validators.msisdn.validateSessionWithToken(
                sid, clientSecret, tokenString
            )
        except IncorrectClientSecretException:
            request.setResponseCode(400)
            return {
                "success": False,
                "errcode": "M_INVALID_PARAM",
                "error": "Client secret does not match the one given when requesting the token",
            }
        except SessionExpiredException:
            request.setResponseCode(400)
            return {
                "success": False,
                "errcode": "M_SESSION_EXPIRED",
                "error": "This validation session has expired: call requestToken again",
            }
        except InvalidSessionIdException:
            request.setResponseCode(400)
            return {
                "success": False,
                "errcode": "M_INVALID_PARAM",
                "error": "The token doesn't match",
            }
        except IncorrectSessionTokenException:
            request.setResponseCode(404)
            return {
                "success": False,
                "errcode": "M_NO_VALID_SESSION",
                "error": "No session could be found with this sid",
            }

    def render_OPTIONS(self, request: Request) -> bytes:
        send_cors(request)
        return b""
