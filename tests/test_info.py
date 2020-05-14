import os

from tests.utils import make_request, make_sydent
from twisted.trial import unittest

from sydent.db.invite_tokens import JoinTokenStore
from sydent.db.threepid_associations import GlobalAssociationStore
from sydent.threepid import ThreepidAssociation
from sydent.util import time_msec


class InfoTestCase(unittest.TestCase):
    """Base class for testing /info and /internal-info endpoints so that every other test
    case can benefit from _query_info.

    Spec for these endpoints can be found here:
        https://github.com/matrix-org/sydent/blob/dinsic/docs/info.md
    """

    def _query_info(
            self,
            address,
            expected_result,
            expected_code=200,
            medium="email",
            internal=False,
    ):
        """Queries /info (or /internal-info if internal is True) with the given address
        and medium, and checks that the response contains the expected body.
        """

        # Figure out which endpoint and servlet to use based on whether internal is True.
        endpoint = "internal-info" if internal else "info"
        servlets = self.sydent.servlets
        servlet = servlets.internalInfo if internal else servlets.info

        # Make the request.
        request, channel = make_request(
            self.sydent.reactor,
            "GET",
            "/_matrix/identity/v1/%s?medium=%s&address=%s" % (endpoint, medium, address),
        )
        request.render(servlet)

        # Check that the result from the response matches what was expected.
        self.assertEqual(channel.code, expected_code)
        if expected_code != 200:
            return

        self.assertDictEqual(channel.json_body, expected_result, channel.json_body)


class InfoNonShadowTestCase(InfoTestCase):

    def setUp(self):
        # Figure out the path to the test info.yaml file.
        info_path = os.path.join(os.path.dirname(__file__), "res/info.yaml")

        # Create a new sydent
        config = {
            "general": {
                # Trust localhost, which is where the requests will be originating from,
                # so we can test that we're doing the right thing with protected
                # homeservers.
                "ips.nonshadow": "127.0.0.1",
                "info_path": info_path,
            }
        }
        self.sydent = make_sydent(config)

        self.sydent.run()

    def test_info(self):
        """Tests the /info endpoint."""

        # Check that using an address with a dedicated entry returns the right result.
        self._query_info(
            address="john.doe@fake.server",
            expected_result={
                "hs": "e.fake.server",
            },
        )

        # Check that using an address matching a pattern which doesn't allow sub-domains
        # returns the right result.
        self._query_info(
            address="john.doe@allowed.server",
            expected_result={
                "hs": "a.fake.server",
            },
        )

        # Check that using an address containing a sub-domain doesn't match a pattern
        # which doesn't allow sub-domains. In this case we fall back to the default
        # value which is e.fake.server.
        self._query_info(
            address="john.doe@notallowed.allowed.server",
            expected_result={
                "hs": "e.fake.server",
            },
        )

        # Check that using an address containing a sub-domain matches a pattern which
        # should allow sub-domains.
        self._query_info(
            address="john.doe@veryvip.vip.fake.server",
            expected_result={
                "hs": "a.fake.server",
            },
        )

        # Check that, when querying from an authorised IP address, using an address
        # matching a pattern for a protected homeserver returns both the public and the
        # protected homeserver.
        self._query_info(
            address="john.doe@internal.fake.server",
            expected_result={
                "hs": "p.fake.server",
                "shadow_hs": "public.p.fake.server",
            },
        )

        # Check that we correctly fall back to the default pattern at the end of the file
        # (.*) if we're using an unknown address.
        self._query_info(
            address="john.doe@unknown.server",
            expected_result={
                "hs": "e.fake.server"
            },
        )

    def test_internal_info(self):
        """Tests the /internal-info endpoint"""

        # Check that using an address with a dedicated entry that doesn't need an invite
        # returns the right result.
        self._query_info(
            address="john.doe@fake.server",
            expected_result={
                "hs": "e.fake.server",
                "invited": False,
                "requires_invite": False,
            },
            internal=True,
        )

        # Check that using an address matching a pattern which doesn't allow sub-domains
        # returns the right result.
        self._query_info(
            address="john.doe@allowed.server",
            expected_result={
                "hs": "a.fake.server",
                "invited": False,
                "requires_invite": False,
            },
            internal=True,
        )

        # Check that using an address containing a sub-domain doesn't match a pattern
        # which doesn't allow sub-domains. In this case we fall back to the default
        # value which is e.fake.server (and requiring an invite).
        self._query_info(
            address="john.doe@notallowed.allowed.server",
            expected_result={
                "hs": "e.fake.server",
                "invited": False,
                "requires_invite": True,
            },
            internal=True,
        )

        # Check that using an address containing a sub-domain matches a pattern which
        # should allow sub-domains.
        self._query_info(
            address="john.doe@veryvip.vip.fake.server",
            expected_result={
                "hs": "a.fake.server",
                "invited": False,
                "requires_invite": False,
            },
            internal=True,
        )

        # Check that using an address matching a pattern for a protected homeserver
        # returns both the public and the protected homeserver.
        # We don't care whether the request comes from an authorised IP address, as
        # /internal-info is expected to be an internal endpoint so any request to it is
        # considered to be originating from a trusted source.
        self._query_info(
            address="john.doe@internal.fake.server",
            expected_result={
                "hs": "p.fake.server",
                "shadow_hs": "public.p.fake.server",
                "invited": False,
                "requires_invite": False,
            },
            internal=True,
        )

        # Check that we correctly fall back to the default pattern at the end of the file
        # (.*) if we're using an unknown address, which matches with the same homeserver
        # as with the first test except it requires an invite.
        self._query_info(
            address="john.doe@unknown.server",
            expected_result={
                "hs": "e.fake.server",
                "invited": False,
                "requires_invite": True,
            },
            internal=True,
        )

    def test_internal_with_invite(self):
        """Tests that the response to a /internal-info request includes an 'invited' key
        set to True if there's an invite stored for this user.
        """

        # Store a fake invite token to make Sydent believe the email address has a
        # pending 3PID invite.
        token_store = JoinTokenStore(self.sydent)
        token_store.storeToken(
            "email",
            "john.doe@unknown.server",
            "!someroom:fake.server",
            "@root:fake.server",
            "sometoken",
        )

        # Check that 'invited' is True in the response from /internal-info.
        self._query_info(
            address="john.doe@unknown.server",
            expected_result={
                "hs": "e.fake.server",
                "invited": True,
                "requires_invite": True,
            },
            internal=True,
        )

    def test_info_existing_user(self):
        """Tests that a response to a /info request includes a new_hs key if the email
        address is already associated with a MXID.
        """

        # Create a fake association.
        assoc = ThreepidAssociation(
            "email",
            "john.doe@allowed.server",
            "somehash",  # We're not checking the hash here so we don't care what's here.
            "@john:e.fake.server",
            time_msec(),
            time_msec()-10000,
            time_msec()+10000,
        )

        # Store the fake association. We only care about the global store since that's
        # where Sydent will check if an address is already associated with an MXID.
        assoc_store = GlobalAssociationStore(self.sydent)
        assoc_store.addAssociation(assoc, "", "", 0)

        # Check that the 'hs' key is the homeserver of the MXID the address is currently
        # associated with, and 'new_hs' is the homeserver matching that email address in
        # the info.yaml file.
        self._query_info(
            address="john.doe@allowed.server",
            expected_result={
                "hs": "e.fake.server",
                "new_hs": "a.fake.server",
            },
        )


class InfoShadowTestCase(InfoTestCase):

    def setUp(self):
        # Figure out the path to the test info.yaml file.
        info_path = os.path.join(os.path.dirname(__file__), "res/info.yaml")

        # Create a new sydent
        config = {
            "general": {
                # We need one nonshadow IP address configured otherwise Sydent will
                # behave as if every IP address is nonshadow.
                "ips.nonshadow": "127.255.255.254",
                "info_path": info_path,
            }
        }
        self.sydent = make_sydent(config)

        self.sydent.run()

    def test_shadow_info(self):
        """Test that /info hides private instances of protected homeservers if queried
        from an untrusted IP address.
        """

        # Check that the response from the /info request doesn't include a 'shadow_hs'
        # key and that its 'hs' key is the public homeserver.
        self._query_info(
            address="john.doe@internal.fake.server",
            expected_result={
                "hs": "public.p.fake.server",
            }
        )

        # Check that /internal-info isn't impacted by whether the IP address the request
        # is coming from. This is because /internal-info is expected to be an internal
        # endpoint so any request to it is considered to be originating from a trusted
        # source.
        self._query_info(
            address="john.doe@internal.fake.server",
            expected_result={
                "hs": "p.fake.server",
                "shadow_hs": "public.p.fake.server",
                "requires_invite": False,
                "invited": False,
            },
            internal=True,
        )
