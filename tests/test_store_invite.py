# Copyright 2021 Matrix.org Foundation C.I.C.
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
from unittest.mock import patch

from parameterized import parameterized
from twisted.trial import unittest

from sydent.users.accounts import Account
from tests.utils import make_request, make_sydent


class StoreInviteTestCase(unittest.TestCase):
    """Tests Sydent's register servlet"""

    def setUp(self) -> None:
        # Create a new sydent
        config = {
            "email": {
                "email.from": "Sydent Validation <noreply@hostname>",
            },
        }
        self.sydent = make_sydent(test_config=config)
        self.sender = "@alice:wonderland"

    @parameterized.expand(
        [
            ("not@an@email@address",),
            ("Naughty Nigel <perfectly.valid@mail.address>",),
        ]
    )
    def test_invalid_email_returns_400(self, address: str) -> None:
        self.sydent.run()

        with patch("sydent.http.servlets.store_invite_servlet.authV2") as authV2:
            authV2.return_value = Account(self.sender, 0, None)

            request, channel = make_request(
                self.sydent.reactor,
                self.sydent.clientApiHttpServer.factory,
                "POST",
                "/_matrix/identity/v2/store-invite",
                content={
                    "address": address,
                    "medium": "email",
                    "room_id": "!myroom:test",
                    "sender": self.sender,
                },
            )

        self.assertEqual(channel.code, 400)
        self.assertEqual(channel.json_body["errcode"], "M_INVALID_EMAIL")
