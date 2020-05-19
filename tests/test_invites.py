from mock import Mock
from sydent.http.httpclient import FederationHttpClient
from sydent.db.invite_tokens import JoinTokenStore
from tests.utils import make_sydent
from twisted.web.client import Response
from twisted.internet import defer
from twisted.trial import unittest


class ThreepidInvitesTestCase(unittest.TestCase):
    """Test that a Sydent can correctly replicate data with another Sydent"""

    def setUp(self):
        # Create a new sydent
        self.sydent = make_sydent()

    def test_delete_on_bind(self):
        self.sydent.run()

        medium = "email"
        address = "john@example.com"

        def post_json_get_nothing(uri, post_json, opts):
            return Response((b'HTTP', 1, 1), 200, b'OK', None, None)

        FederationHttpClient.post_json_get_nothing = Mock(
            side_effect=post_json_get_nothing,
        )

        join_token_store = JoinTokenStore(self.sydent)
        join_token_store.storeToken(
            medium, address, "!someroom:example.com", "@jane:example.com",
            "sometoken",
        )

        tokens = join_token_store.getTokens(medium, address)
        self.assertEqual(len(tokens), 1, tokens)

        self.sydent.threepidBinder.addBinding(
            medium, address, "@john:example.com",
        )

        self.sydent.reactor.advance(1000)

        cur = self.sydent.db.cursor()

        res = cur.execute(
            "SELECT medium, address, room_id, sender, token FROM invite_tokens"
            " WHERE medium = ? AND address = ?",
            (medium, address,)
        )
        rows = res.fetchall()

        self.assertEqual(len(rows), 0, rows)


class ThreepidInvitesNoDeleteTestCase(unittest.TestCase):
    """Test that a Sydent can correctly replicate data with another Sydent"""

    def setUp(self):
        # Create a new sydent
        config = {
            "general": {
                "delete_tokens_on_bind": "false"
            }
        }
        self.sydent = make_sydent(test_config=config)

    def test_no_delete_on_bind(self):
        self.sydent.run()

        medium = "email"
        address = "john@example.com"

        def post_json_get_nothing(uri, post_json, opts):
            return Response((b'HTTP', 1, 1), 200, b'OK', None, None)

        FederationHttpClient.post_json_get_nothing = Mock(
            side_effect=post_json_get_nothing,
        )

        join_token_store = JoinTokenStore(self.sydent)
        join_token_store.storeToken(
            medium, address, "!someroom:example.com", "@jane:example.com",
            "sometoken",
        )

        tokens = join_token_store.getTokens(medium, address)
        self.assertEqual(len(tokens), 1, tokens)

        self.sydent.threepidBinder.addBinding(
            medium, address, "@john:example.com",
        )

        self.sydent.reactor.advance(1000)

        cur = self.sydent.db.cursor()

        res = cur.execute(
            "SELECT medium, address, room_id, sender, token FROM invite_tokens"
            " WHERE medium = ? AND address = ?",
            (medium, address,)
        )
        rows = res.fetchall()

        self.assertEqual(len(rows), 1, rows)
