#  Copyright 2021 The Matrix.org Foundation C.I.C.
#
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

import os.path
from mock import Mock, patch

from twisted.web.client import Response
from twisted.trial import unittest

from sydent.db.invite_tokens import JoinTokenStore
from sydent.http.httpclient import FederationHttpClient
from sydent.http.servlets.store_invite_servlet import StoreInviteServlet
from tests.utils import make_request, make_sydent


class TestRequestCode(unittest.TestCase):
    def setUp(self):
        # Create a new sydent
        config = {
            "general": {
                "templates.path": os.path.join(os.path.dirname(os.path.dirname(__file__)), "res"),
            },
        }
        self.sydent = make_sydent(test_config=config)

    def _render_request(self, request):
        # Patch out the email sending so we can investigate the resulting email.
        with patch("sydent.util.emailutils.smtplib") as smtplib:
            request.render(self.sydent.servlets.emailRequestCode)

        # Fish out the SMTP object and return it.
        smtp = smtplib.SMTP.return_value
        smtp.sendmail.assert_called_once()

        return smtp

    def test_request_code(self):
        self.sydent.run()

        request, channel = make_request(
            self.sydent.reactor, "POST", "/_matrix/identity/v1/validate/email/requestToken",
            {
                "email": "test@test",
                "client_secret": "oursecret",
                "send_attempt": 0,
            }
        )
        smtp = self._render_request(request)
        self.assertEqual(channel.code, 200)

        # Ensure the email is as expected.
        email_contents = smtp.sendmail.call_args[0][2].decode("utf-8")
        self.assertIn("Confirm your email address for Matrix", email_contents)

    def test_branded_request_code(self):
        self.sydent.run()

        request, channel = make_request(
            self.sydent.reactor, "POST", "/_matrix/identity/v1/validate/email/requestToken?brand=vector-im",
            {
                "email": "test@test",
                "client_secret": "oursecret",
                "send_attempt": 0,
            }
        )
        smtp = self._render_request(request)
        self.assertEqual(channel.code, 200)

        # Ensure the email is as expected.
        email_contents = smtp.sendmail.call_args[0][2].decode("utf-8")
        self.assertIn("Confirm your email address for Element", email_contents)
