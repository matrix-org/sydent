# Copyright 2015 OpenMarket Ltd
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

import random
import string
from email.header import Header
from http import HTTPStatus
from typing import TYPE_CHECKING

import nacl.signing
from twisted.web.resource import Resource
from twisted.web.server import Request
from unpaddedbase64 import encode_base64

from sydent.db.invite_tokens import JoinTokenStore
from sydent.db.threepid_associations import GlobalAssociationStore
from sydent.http.auth import authV2
from sydent.http.servlets import MatrixRestError, get_args, jsonwrap, send_cors
from sydent.types import JsonDict
from sydent.util.emailutils import EmailAddressException, sendEmail
from sydent.util.stringutils import MAX_EMAIL_ADDRESS_LENGTH, normalise_address

if TYPE_CHECKING:
    from sydent.sydent import Sydent


class StoreInviteServlet(Resource):
    def __init__(self, syd: "Sydent", require_auth: bool = False) -> None:
        self.sydent = syd
        self.random = random.SystemRandom()
        self.require_auth = require_auth

    @jsonwrap
    def render_POST(self, request: Request) -> JsonDict:
        send_cors(request)

        args = get_args(
            request,
            (
                "medium",
                "address",
                "room_id",
                "sender",
            ),
        )
        medium = args["medium"]
        address = args["address"]
        roomId = args["room_id"]
        sender = args["sender"]

        # ensure we are casefolding email address before storing
        normalised_address = normalise_address(address, medium)

        verified_sender = None
        if self.require_auth:
            account = authV2(self.sydent, request)
            verified_sender = sender
            if account.userId != sender:
                raise MatrixRestError(403, "M_UNAUTHORIZED", "'sender' doesn't match")

        globalAssocStore = GlobalAssociationStore(self.sydent)
        mxid = globalAssocStore.getMxid(medium, normalised_address)
        if mxid:
            request.setResponseCode(400)
            return {
                "errcode": "M_THREEPID_IN_USE",
                "error": "Binding already known",
                "mxid": mxid,
            }

        if medium != "email":
            request.setResponseCode(400)
            return {
                "errcode": "M_UNRECOGNIZED",
                "error": "Didn't understand medium '%s'" % (medium,),
            }

        if not (0 < len(address) <= MAX_EMAIL_ADDRESS_LENGTH):
            request.setResponseCode(400)
            return {"errcode": "M_INVALID_PARAM", "error": "Invalid email provided"}

        token = self._randomString(128)

        tokenStore = JoinTokenStore(self.sydent)

        ephemeralPrivateKey = nacl.signing.SigningKey.generate()
        ephemeralPublicKey = ephemeralPrivateKey.verify_key

        ephemeralPrivateKeyBase64 = encode_base64(ephemeralPrivateKey.encode(), True)
        ephemeralPublicKeyBase64 = encode_base64(ephemeralPublicKey.encode(), True)

        tokenStore.storeEphemeralPublicKey(ephemeralPublicKeyBase64)
        tokenStore.storeToken(medium, normalised_address, roomId, sender, token)

        # Variables to substitute in the template.
        substitutions = {}
        # Include all arguments sent via the request.
        for k, v in args.items():
            if isinstance(v, str):
                substitutions[k] = v
        substitutions["token"] = token

        # Substitutions that the template requires, but are optional to provide
        # to the API.
        extra_substitutions = [
            "sender_display_name",
            "token",
            "room_name",
            "bracketed_room_name",
            "room_avatar_url",
            "sender_avatar_url",
            "guest_user_id",
            "guest_access_token",
            "room_type",
        ]
        for k in extra_substitutions:
            substitutions.setdefault(k, "")

        substitutions["bracketed_verified_sender"] = ""
        if verified_sender:
            substitutions["bracketed_verified_sender"] = "(%s) " % (verified_sender,)

        substitutions["ephemeral_private_key"] = ephemeralPrivateKeyBase64
        if substitutions["room_name"] != "":
            substitutions["bracketed_room_name"] = "(%s) " % substitutions["room_name"]

        substitutions[
            "web_client_location"
        ] = self.sydent.config.email.default_web_client_location
        if "org.matrix.web_client_location" in substitutions:
            substitutions["web_client_location"] = substitutions[
                "org.matrix.web_client_location"
            ]

        if substitutions["room_type"] == "m.space":
            subject = self.sydent.config.email.invite_subject_space % substitutions
        else:
            subject = self.sydent.config.email.invite_subject % substitutions

        substitutions["subject_header_value"] = Header(subject, "utf8").encode()

        brand = self.sydent.brand_from_request(request)

        # self.sydent.config.email.invite_template is deprecated
        if self.sydent.config.email.invite_template is None:
            templateFile = self.sydent.get_branded_template(
                brand,
                "invite_template.eml",
            )
        else:
            templateFile = self.sydent.config.email.invite_template

        try:
            sendEmail(self.sydent, templateFile, normalised_address, substitutions)
        except EmailAddressException:
            request.setResponseCode(HTTPStatus.BAD_REQUEST)
            return {"errcode": "M_INVALID_EMAIL", "error": "Invalid email address"}

        pubKey = self.sydent.keyring.ed25519.verify_key
        pubKeyBase64 = encode_base64(pubKey.encode())

        baseUrl = "%s/_matrix/identity/api/v1" % (
            self.sydent.config.http.server_http_url_base,
        )

        keysToReturn = []
        keysToReturn.append(
            {
                "public_key": pubKeyBase64,
                "key_validity_url": baseUrl + "/pubkey/isvalid",
            }
        )
        keysToReturn.append(
            {
                "public_key": ephemeralPublicKeyBase64,
                "key_validity_url": baseUrl + "/pubkey/ephemeral/isvalid",
            }
        )

        resp = {
            "token": token,
            "public_key": pubKeyBase64,
            "public_keys": keysToReturn,
            "display_name": self.redact_email_address(address),
        }

        return resp

    def redact_email_address(self, address: str) -> str:
        """
        Redacts the content of a 3PID address. Redacts both the email's username and
        domain independently.

        :param address: The address to redact.

        :return: The redacted address.
        """
        # Extract strings from the address
        username, domain = address.split("@", 1)

        # Obfuscate strings
        redacted_username = self._redact(
            username, self.sydent.config.email.username_obfuscate_characters
        )
        redacted_domain = self._redact(
            domain, self.sydent.config.email.domain_obfuscate_characters
        )

        return redacted_username + "@" + redacted_domain

    def _redact(self, s: str, characters_to_reveal: int) -> str:
        """
        Redacts the content of a string, using a given amount of characters to reveal.
        If the string is shorter than the given threshold, redact it based on length.

        :param s: The string to redact.

        :param characters_to_reveal: How many characters of the string to leave before
            the '...'

        :return: The redacted string.
        """
        # If the string is shorter than the defined threshold, redact based on length
        if len(s) <= characters_to_reveal:
            if len(s) > 5:
                return s[:3] + "..."
            if len(s) > 1:
                return s[0] + "..."
            return "..."

        # Otherwise truncate it and add an ellipses
        return s[:characters_to_reveal] + "..."

    def _randomString(self, length: int) -> str:
        """
        Generate a random string of the given length.

        :param length: The length of the string to generate.

        :return: The generated string.
        """
        return "".join(self.random.choice(string.ascii_letters) for _ in range(length))
