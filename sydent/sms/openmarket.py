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
from typing import TYPE_CHECKING, Dict, Optional

from twisted.web.http_headers import Headers

from sydent.http.httpclient import SimpleHttpClient

if TYPE_CHECKING:
    from sydent.sydent import Sydent

logger = logging.getLogger(__name__)


API_BASE_URL = "https://smsc.openmarket.com/sms/v4/mt"
# The Customer Integration Environment, where you can send
# the same requests but it doesn't actually send any SMS.
# Useful for testing.
# API_BASE_URL = "http://smsc-cie.openmarket.com/sms/v4/mt"

# The TON (ie. Type of Number) codes by type used in our config file
TONS = {
    "long": 1,
    "short": 3,
    "alpha": 5,
}


def tonFromType(t: str) -> int:
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
        send_body = {
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

        # Make sure username and password are bytes otherwise we can't use them with
        # b64encode.
        username = self.sydent.cfg.get("sms", "username").encode("UTF-8")
        password = self.sydent.cfg.get("sms", "password").encode("UTF-8")

        b64creds = b64encode(b"%s:%s" % (username, password))
        req_headers = Headers(
            {
                b"Authorization": [b"Basic " + b64creds],
                b"Content-Type": [b"application/json"],
            }
        )

        resp = await self.http_cli.post_json_get_nothing(
            API_BASE_URL, send_body, {"headers": req_headers}
        )
        headers = dict(resp.headers.getAllRawHeaders())

        if "Location" not in headers:
            raise Exception("Got response from sending SMS with no location header")
        # Nominally we should parse the URL, but we can just split on '/' since
        # we only care about the last part.
        parts = headers["Location"][0].split("/")
        if len(parts) < 2:
            raise Exception(
                "Got response from sending SMS with malformed location header"
            )
