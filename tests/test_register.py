# Copyright 2021 The Matrix.org Foundation C.I.C.
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
from http import HTTPStatus
from json import JSONDecodeError
from unittest.mock import patch

import twisted.internet.error
import twisted.web.client
from parameterized import parameterized
from twisted.trial import unittest

from tests.utils import make_request, make_sydent


class RegisterTestCase(unittest.TestCase):
    """Tests Sydent's register servlet"""

    def setUp(self) -> None:
        # Create a new sydent
        self.sydent = make_sydent()

    def test_sydent_rejects_invalid_hostname(self) -> None:
        """Tests that the /register endpoint rejects an invalid hostname passed as matrix_server_name"""
        self.sydent.run()

        bad_hostname = "example.com#"

        request, channel = make_request(
            self.sydent.reactor,
            self.sydent.clientApiHttpServer.factory,
            "POST",
            "/_matrix/identity/v2/account/register",
            content={"matrix_server_name": bad_hostname, "access_token": "foo"},
        )

        self.assertEqual(channel.code, 400)

    @parameterized.expand(
        [
            (twisted.internet.error.DNSLookupError(),),
            (twisted.internet.error.TimeoutError(),),
            (twisted.internet.error.ConnectionRefusedError(),),
            # Naughty: strictly we're supposed to initialise a ResponseNeverReceived
            # with a list of 1 or more failures.
            (twisted.web.client.ResponseNeverReceived([]),),
        ]
    )
    def test_connection_failure(self, exc: Exception) -> None:
        self.sydent.run()
        with patch(
            "sydent.http.httpclient.FederationHttpClient.get_json", side_effect=exc
        ):
            request, channel = make_request(
                self.sydent.reactor,
                self.sydent.clientApiHttpServer.factory,
                "POST",
                "/_matrix/identity/v2/account/register",
                content={
                    "matrix_server_name": "matrix.alice.com",
                    "access_token": "back_in_wonderland",
                },
            )
        self.assertEqual(channel.code, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.assertEqual(channel.json_body["errcode"], "M_UNKNOWN")
        # Check that we haven't just returned the generic error message in asyncjsonwrap
        self.assertNotEqual(channel.json_body["error"], "Internal Server Error")
        self.assertIn("contact", channel.json_body["error"])

    def test_federation_does_not_return_json(self) -> None:
        self.sydent.run()
        exc = JSONDecodeError("ruh roh", "C'est n'est pas une objet JSON", 0)
        with patch(
            "sydent.http.httpclient.FederationHttpClient.get_json", side_effect=exc
        ):
            request, channel = make_request(
                self.sydent.reactor,
                self.sydent.clientApiHttpServer.factory,
                "POST",
                "/_matrix/identity/v2/account/register",
                content={
                    "matrix_server_name": "matrix.alice.com",
                    "access_token": "back_in_wonderland",
                },
            )
        self.assertEqual(channel.code, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.assertEqual(channel.json_body["errcode"], "M_UNKNOWN")
        # Check that we haven't just returned the generic error message in asyncjsonwrap
        self.assertNotEqual(channel.json_body["error"], "Internal Server Error")
        self.assertIn("JSON", channel.json_body["error"])
