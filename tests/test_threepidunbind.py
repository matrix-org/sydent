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
from unittest.mock import patch

import twisted.internet.error
import twisted.web.client
from parameterized import parameterized
from twisted.trial import unittest

from tests.utils import make_request, make_sydent


class ThreepidUnbindTestCase(unittest.TestCase):
    """Tests Sydent's threepidunbind servlet"""

    def setUp(self) -> None:
        # Create a new sydent
        self.sydent = make_sydent()

    # Duplicated from TestRegisterServelet. Is there a way for us to keep
    # ourselves DRY?
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
        """Check we respond sensibly if we can't contact the homeserver."""
        self.sydent.run()
        with patch.object(
            self.sydent.sig_verifier, "authenticate_request", side_effect=exc
        ):
            request, channel = make_request(
                self.sydent.reactor,
                self.sydent.clientApiHttpServer.factory,
                "POST",
                "/_matrix/identity/v2/3pid/unbind",
                content={
                    "mxid": "@alice:wonderland",
                    "threepid": {
                        "address": "alice.cooper@wonderland.biz",
                        "medium": "email",
                    },
                },
            )
        self.assertEqual(channel.code, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.assertEqual(channel.json_body["errcode"], "M_UNKNOWN")
        self.assertIn("contact", channel.json_body["error"])
