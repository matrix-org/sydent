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

from typing import TYPE_CHECKING, Optional

from twisted.web.server import Request

from sydent.http.auth import authV2
from sydent.http.servlets import SydentResource, get_args, jsonwrap, send_cors
from sydent.types import JsonDict
from sydent.util.emailutils import EmailAddressException, EmailSendException
from sydent.util.stringutils import MAX_EMAIL_ADDRESS_LENGTH, is_valid_client_secret
from sydent.validators import (
    IncorrectClientSecretException,
    IncorrectSessionTokenException,
    InvalidSessionIdException,
    SessionExpiredException,
)

if TYPE_CHECKING:
    from sydent.sydent import Sydent


class EmailRequestCodeServlet(SydentResource):
    isLeaf = True

    def __init__(self, syd: "Sydent", require_auth: bool = False) -> None:
        super().__init__()
        self.sydent = syd
        self.require_auth = require_auth

    @jsonwrap
    def render_POST(self, request: Request) -> JsonDict:
        send_cors(request)

        ipaddress = self.sydent.ip_from_request(request)

        if self.require_auth:
            account = authV2(self.sydent, request)

            self.sydent.email_sender_ratelimiter.ratelimit(account.userId)
        elif ipaddress:
            # For `/v1/` requests the ip address is the best we can do for rate
            # limiting.
            self.sydent.email_sender_ratelimiter.ratelimit(ipaddress)

        args = get_args(request, ("email", "client_secret", "send_attempt"))

        email = args["email"]
        clientSecret = args["client_secret"]

        try:
            # if we got this via the v1 API in a querystring or urlencoded body,
            # then the values in args will be a string. So check that
            # send_attempt is an int.
            #
            # NB: We don't check if we're processing a url-encoded v1 request.
            # This means we accept string representations of integers for
            # `send_attempt` in v2 requests, and in v1 requests that supply a
            # JSON body. This is contrary to the spec and leaves me with a dirty
            # feeling I can't quite shake off.
            #
            # Where's Raymond Hettinger when you need him? (THUMP) There must be
            # a better way!
            sendAttempt = int(args["send_attempt"])
        except (TypeError, ValueError):
            request.setResponseCode(400)
            return {
                "errcode": "M_INVALID_PARAM",
                "error": f"send_attempt should be an integer (got {args['send_attempt']}",
            }

        if not is_valid_client_secret(clientSecret):
            request.setResponseCode(400)
            return {
                "errcode": "M_INVALID_PARAM",
                "error": "Invalid client_secret provided",
            }

        if not (0 < len(email) <= MAX_EMAIL_ADDRESS_LENGTH):
            request.setResponseCode(400)
            return {"errcode": "M_INVALID_PARAM", "error": "Invalid email provided"}

        brand = self.sydent.brand_from_request(request)

        nextLink: Optional[str] = None
        if "next_link" in args and not args["next_link"].startswith("file:///"):
            nextLink = args["next_link"]

        try:
            sid = self.sydent.validators.email.requestToken(
                email,
                clientSecret,
                sendAttempt,
                nextLink,
                ipaddress=ipaddress,
                brand=brand,
            )
            resp = {"sid": str(sid)}
        except EmailAddressException:
            request.setResponseCode(400)
            resp = {"errcode": "M_INVALID_EMAIL", "error": "Invalid email address"}
        except EmailSendException:
            request.setResponseCode(500)
            resp = {"errcode": "M_EMAIL_SEND_ERROR", "error": "Failed to send email"}

        return resp

    def render_OPTIONS(self, request: Request) -> bytes:
        send_cors(request)
        return b""


class EmailValidateCodeServlet(SydentResource):
    isLeaf = True

    def __init__(self, syd: "Sydent", require_auth: bool = False) -> None:
        super().__init__()
        self.sydent = syd
        self.require_auth = require_auth

    def render_GET(self, request: Request) -> bytes:
        args = get_args(request, ("nextLink",), required=False)

        resp = None
        try:
            resp = self.do_validate_request(request)
        except Exception:
            pass
        if resp and "success" in resp and resp["success"]:
            msg = "Verification successful! Please return to your Matrix client to continue."
            if "nextLink" in args:
                next_link = args["nextLink"]
                if not next_link.startswith("file:///"):
                    request.setResponseCode(302)
                    request.setHeader("Location", next_link)
        else:
            msg = "Verification failed: you may need to request another verification email"

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
        res = open(templateFile).read() % {"message": msg}

        return res.encode("UTF-8")

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
            return self.sydent.validators.email.validateSessionWithToken(
                sid, clientSecret, tokenString
            )
        except IncorrectClientSecretException:
            return {
                "success": False,
                "errcode": "M_INVALID_PARAM",
                "error": "Client secret does not match the one given when requesting the token",
            }
        except SessionExpiredException:
            return {
                "success": False,
                "errcode": "M_SESSION_EXPIRED",
                "error": "This validation session has expired: call requestToken again",
            }
        except InvalidSessionIdException:
            return {
                "success": False,
                "errcode": "M_INVALID_PARAM",
                "error": "The token doesn't match",
            }
        except IncorrectSessionTokenException:
            return {
                "success": False,
                "errcode": "M_NO_VALID_SESSION",
                "error": "No session could be found with this sid",
            }

    def render_OPTIONS(self, request: Request) -> bytes:
        send_cors(request)
        return b""
