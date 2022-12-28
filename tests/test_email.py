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

from typing import Optional
from unittest.mock import Mock, patch

from twisted.trial import unittest

from sydent.types import JsonDict
from tests.utils import make_request, make_sydent


class TestRequestCode(unittest.TestCase):
    def setUp(self) -> None:
        # Create a new sydent
        self.sydent = make_sydent()

    def _make_request(self, url: str, body: Optional[JsonDict] = None) -> Mock:
        # Patch out the email sending so we can investigate the resulting email.
        with patch("sydent.util.emailutils.smtplib") as smtplib:
            request, channel = make_request(
                self.sydent.reactor,
                self.sydent.clientApiHttpServer.factory,
                "POST",
                url,
                body,
            )

        self.assertEqual(channel.code, 200)

        # Fish out the SMTP object and return it.
        smtp = smtplib.SMTP.return_value
        smtp.sendmail.assert_called_once()

        return smtp

    def test_request_code(self) -> None:
        self.sydent.run()

        smtp = self._make_request(
            "/_matrix/identity/api/v1/validate/email/requestToken",
            {
                "email": "test@test",
                "client_secret": "oursecret",
                "send_attempt": 0,
            },
        )

        # Ensure the email is as expected.
        email_contents = smtp.sendmail.call_args[0][2].decode("utf-8")
        self.assertIn("Confirm your email address for Matrix", email_contents)

    def test_request_code_via_url_query_params(self) -> None:
        self.sydent.run()
        url = (
            "/_matrix/identity/api/v1/validate/email/requestToken?"
            "email=test@test"
            "&client_secret=oursecret"
            "&send_attempt=0"
        )
        smtp = self._make_request(url)

        # Ensure the email is as expected.
        email_contents = smtp.sendmail.call_args[0][2].decode("utf-8")
        self.assertIn("Confirm your email address for Matrix", email_contents)

    def test_branded_request_code(self) -> None:
        self.sydent.run()

        smtp = self._make_request(
            "/_matrix/identity/api/v1/validate/email/requestToken?brand=vector-im",
            {
                "email": "test@test",
                "client_secret": "oursecret",
                "send_attempt": 0,
            },
        )

        # Ensure the email is as expected.
        email_contents = smtp.sendmail.call_args[0][2].decode("utf-8")
        self.assertIn("Confirm your email address for Element", email_contents)
