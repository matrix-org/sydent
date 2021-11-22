#  Copyright 2021 The Matrix.org Foundation C.I.C.
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
import asyncio
import os.path
from typing import Awaitable
from unittest.mock import MagicMock, patch

import attr
from twisted.trial import unittest
from twisted.web.server import Request

from tests.utils import make_request, make_sydent


@attr.s(auto_attribs=True)
class FakeHeader:
    """
    A fake header object
    """

    headers: dict

    def getAllRawHeaders(self):
        return self.headers


@attr.s(auto_attribs=True)
class FakeResponse:
    """A fake twisted.web.IResponse object"""

    # HTTP response code
    code: int

    # Fake Header
    headers: FakeHeader


class TestRequestCode(unittest.TestCase):
    def setUp(self) -> None:
        # Create a new sydent
        config = {
            "general": {
                "templates.path": os.path.join(
                    os.path.dirname(os.path.dirname(__file__)), "res"
                ),
            },
        }
        self.sydent = make_sydent(test_config=config)

    def _render_request(self, request: Request) -> Awaitable[MagicMock]:
        # Patch out the email sending so we can investigate the resulting email.
        with patch("sydent.sms.openmarket.OpenMarketSMS.sendTextSMS") as sendTextSMS:
            # We can't use AsyncMock until Python 3.8. Instead, mock the
            # function as returning a future.
            f = asyncio.Future()
            f.set_result(MagicMock())
            sendTextSMS.return_value = f
            request.render(self.sydent.servlets.msisdnRequestCode)

        return sendTextSMS

    def test_request_code(self) -> None:
        self.sydent.run()

        request, channel = make_request(
            self.sydent.reactor,
            "POST",
            "/_matrix/identity/api/v1/validate/msisdn/requestToken",
            {
                "phone_number": "447700900750",
                "country": "GB",
                "client_secret": "oursecret",
                "send_attempt": 0,
            },
        )
        sendSMS_mock = self._render_request(request)
        sendSMS_mock.assert_called_once()
        self.assertEqual(channel.code, 200)

    def test_request_code_via_url_query_params(self) -> None:
        self.sydent.run()
        url = (
            "/_matrix/identity/api/v1/validate/msisdn/requestToken?"
            "phone_number=447700900750"
            "&country=GB"
            "&client_secret=oursecret"
            "&send_attempt=0"
        )
        request, channel = make_request(self.sydent.reactor, "POST", url)
        sendSMS_mock = self._render_request(request)
        sendSMS_mock.assert_called_once()
        self.assertEqual(channel.code, 200)

    @patch("sydent.http.httpclient.HTTPClient.post_json_maybe_get_json")
    def test_bad_api_response_raises_exception(self, post_json: MagicMock) -> None:
        """Test that an error response from OpenMarket raises an exception
        and that the requester receives an error code."""

        header = FakeHeader({})
        resp = FakeResponse(code=400, headers=header), {}
        post_json.return_value = resp
        self.sydent.run()
        request, channel = make_request(
            self.sydent.reactor,
            "POST",
            "/_matrix/identity/api/v1/validate/msisdn/requestToken",
            {
                "phone_number": "447700900750",
                "country": "GB",
                "client_secret": "oursecret",
                "send_attempt": 0,
            },
        )
        request.render(self.sydent.servlets.msisdnRequestCode)
        self.assertEqual(channel.code, 500)
