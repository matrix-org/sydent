import email.utils
import os.path
from unittest.mock import patch

from twisted.trial import unittest

from sydent.users.accounts import Account
from tests.utils import make_request, make_sydent


class StoreInviteTestCase(unittest.TestCase):
    """Tests Sydent's register servlet"""

    def setUp(self) -> None:
        # Create a new sydent
        config = {
            "general": {
                "templates.path": os.path.join(
                    os.path.dirname(os.path.dirname(__file__)), "res"
                ),
            },
            "email": {
                "email.from": "Sydent Validation <noreply@hostname>",
            },
        }
        self.sydent = make_sydent(test_config=config)
        self.sender = "@alice:wonderland"

    def test_invalid_email_returns_400(self) -> None:
        self.sydent.run()
        invalid_email = "not@an@email@address"
        # Email addresses are complicated (see RFCs 5321, 5322 and 6531; plus
        # https://www.netmeister.org/blog/email.html). So let's sanity check
        # that Python's stdlib considers that invalid.
        self.assertEqual(email.utils.parseaddr(invalid_email), ("", ""))

        request, channel = make_request(
            self.sydent.reactor,
            "POST",
            "/_matrix/identity/v2/account/store-invite",
            content={
                "address": "not@an@email@address",
                "medium": "email",
                "room_id": "!myroom:test",
                "sender": self.sender,
            },
        )

        with patch("sydent.http.servlets.store_invite_servlet.authV2") as authV2:
            authV2.return_value = Account(self.sender, 0, None)
            request.render(self.sydent.servlets.storeInviteServletV2)

        self.assertEqual(channel.code, 400)
        self.assertEqual(channel.json_body["errcode"], "M_INVALID_EMAIL")
