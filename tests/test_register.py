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

from twisted.trial import unittest

from tests.utils import make_request, make_sydent


class RegisterTestCase(unittest.TestCase):
    """Tests Sydent's register servlet"""

    def setUp(self):
        # Create a new sydent
        self.sydent = make_sydent()

    def test_sydent_rejects_invalid_hostname(self):
        """Tests that the /register endpoint rejects an invalid hostname passed as matrix_server_name"""
        self.sydent.run()

        bad_hostname = "example.com#"

        request, channel = make_request(
            self.sydent.reactor,
            "POST",
            "/_matrix/identity/v2/account/register",
            content={"matrix_server_name": bad_hostname, "access_token": "foo"},
        )

        request.render(self.sydent.servlets.registerServlet)

        self.assertEqual(channel.code, 400)
