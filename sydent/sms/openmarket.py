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
from base64 import b64encode
from typing import TYPE_CHECKING, Dict, Optional, cast

from twisted.web.http_headers import Headers

from sydent.http.httpclient import SimpleHttpClient
from sydent.sms.types import SendSMSBody, TypeOfNumber
from sydent.types import JsonDict

if TYPE_CHECKING:
    from sydent.sydent import Sydent

logger = logging.getLogger(__name__)


API_BASE_URL = "https://smsc.openmarket.com/sms/v4/mt"
# The Customer Integration Environment, where you can send
# the same requests but it doesn't actually send any SMS.
# Useful for testing.
# API_BASE_URL = "http://smsc-cie.openmarket.com/sms/v4/mt"

# The TON (ie. Type of Number) codes by type used in our config file
TONS: Dict[str, TypeOfNumber] = {
    "long": 1,
    "short": 3,
    "alpha": 5,
}


def tonFromType(t: str) -> TypeOfNumber:
    """
    Get the type of number from the originator's type.

    :param t: Type from the originator.
    :type t: str

    :return: The type of number.
    :rtype: int
    """
    if t in TONS:
        return TONS[t]
    raise Exception("Unknown number type (%s) for originator" % t)


class OpenMarketSMS:
    def __init__(self, sydent: "Sydent") -> None:
        self.sydent = sydent
        self.http_cli = SimpleHttpClient(sydent)

    async def sendTextSMS(
        self, body: str, dest: str, source: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Sends a text message with the given body to the given MSISDN.

        :param body: The message to send.
        :param dest: The destination MSISDN to send the text message to.
        """
        send_body: SendSMSBody = {
            "mobileTerminate": {
                "message": {"content": body, "type": "text"},
                "destination": {
                    "address": dest,
                },
            },
        }
        if source:
            send_body["mobileTerminate"]["source"] = {
                "ton": tonFromType(source["type"]),
                "address": source["text"],
            }

        username = self.sydent.config.sms.api_username
        password = self.sydent.config.sms.api_password

        b64creds = b64encode(b"%s:%s" % (username, password))
        req_headers = Headers(
            {
                b"Authorization": [b"Basic " + b64creds],
                b"Content-Type": [b"application/json"],
            }
        )

        # Type safety: The case from a TypedDict to a regular Dict is required
        # because the two are deliberately not compatible. See
        #    https://github.com/python/mypy/issues/4976
        # for details, but in a nutshell: Dicts can have keys added or removed,
        # and that would break the invariants that a TypedDict is there to check.
        # The case below is safe because we never use send_body afterwards.
        resp, response_body = await self.http_cli.post_json_maybe_get_json(
            API_BASE_URL, cast(JsonDict, send_body), {"headers": req_headers}
        )

        headers = dict(resp.headers.getAllRawHeaders())

        request_id = None
        if b"X-Request-Id" in headers:
            request_id = headers[b"X-Request-Id"][0].decode("UTF-8")

        # Catch errors from the API. The documentation says a success code should be 202
        # Accepted, but let's be broad here just in case and accept all 2xx response
        # codes.
        #
        # Relevant OpenMarket API documentation:
        # https://www.openmarket.com/docs/Content/apis/v4http/send-json.htm
        if resp.code < 200 or resp.code >= 300:
            if response_body is None or "error" not in response_body:
                raise Exception(
                    "OpenMarket API responded with status %d (request ID: %s)"
                    % (
                        resp.code,
                        request_id,
                    ),
                )

            error = response_body["error"]
            raise Exception(
                "OpenMarket API responded with status %d (request ID: %s): %s"
                % (
                    resp.code,
                    request_id,
                    error,
                ),
            )

        ticket_id = None
        if b"Location" not in headers:
            logger.error("Got response from sending SMS with no location header")
        else:
            # Nominally we should parse the URL, but we can just split on '/' since
            # we only care about the last part.
            value = headers[b"Location"][0].decode("UTF-8")
            parts = value.split("/")
            if len(parts) < 2:
                logger.error(
                    "Got response from sending SMS with malformed location header: %s",
                    value,
                )
                return
            else:
                ticket_id = parts[-1]

        logger.info(
            "Successfully sent SMS (ticket ID: %s, request ID %s), OpenMarket API"
            " responded with code %d",
            ticket_id,
            request_id,
            resp.code,
        )
