import json

import signedjson.key
import signedjson.sign

from mock import Mock
from tests.utils import make_request, make_sydent
from twisted.trial import unittest


class UserdirTestCase(unittest.TestCase):

    def setUp(self):
        # Create a new sydent
        config = {
            "userdir": {
                "userdir.allowed_homeservers": "fake.server"
            }
        }

        # Use this keypair to sign and verify payloads.
        self.signing_key = signedjson.key.decode_signing_key_base64(
            "ed25519", "0", "b29eXMMAYCFvFEtq9mLI42aivMtcg4Hl0wK89a+Vb6c",
        )
        self.public_key_base64 = "+vB8mTaooD/MA8YYZM8t9+vnGhP1937q2icrqPV9JTs"

        self.sydent = make_sydent(test_config=config)

        # Mock the _getKeysForServer function so tests don't fail on fetching keys.
        self.sydent.sig_verifier._getKeysForServer = Mock()
        pubkey_res = {"ed25519:0": {"key": self.public_key_base64}}
        self.sydent.sig_verifier._getKeysForServer.return_value = pubkey_res

        self.sydent.run()

    def test_replicate_profile_and_lookup(self):
        """Tests that a user can send profile updates via the corresponding replication
        endpoint and that the user directory is populated correctly."""

        # Create two profiles. Jane Doe is an extra profile we're not going to look up to
        # ensure filtering is applied.
        john_update = {
            "display_name": "John Doe",
            "avatar_url": "mxc://fake.server/someavatar",
        }
        jane_update = {
            "display_name": "Jane Doe",
            "avatar_url": "mxc://fake.server/someotheravatar",
        }
        self._update_profiles(
            batchnum=1,
            batch={
                "@john:fake.server": john_update,
                "@jane:fake.server": jane_update,
            },
        )

        # Check that John's profile exists and is returned by a lookup.
        self._query_profile_for_search_terms("John", john_update)

        # Check that updating the profile of a user to None removes that profile from the
        # user directory.
        self._update_profiles(
            batchnum=2,
            batch={
                "@john:fake.server": None,
            },
        )
        self._query_profile_for_search_terms("John", None)

        # Check that updating a profile but not increasing the batch number doesn't
        # update the user directory.
        self._update_profiles(
            batchnum=2,
            batch={
                "@john:fake.server": john_update,
            },
        )
        self._query_profile_for_search_terms("John", None)

    def _update_profiles(self, batchnum, batch):
        """Send the given profile updates."""

        # Build and sign the request body.
        profile_update = {
            "batchnum": batchnum,
            "batch": batch,
            "origin_server": "fake.server",
        }
        signed_update = signedjson.sign.sign_json(
            profile_update, "fake.server", self.signing_key,
        )

        # Send the profile updates.
        request, channel = make_request(
            self.sydent.reactor,
            "POST",
            "/_matrix/identity/api/v1/replicate_profiles",
            json.dumps(signed_update),
        )
        request.render(self.sydent.servlets.profileReplicationServlet)

        self.assertEqual(channel.code, 200, channel.json_body)

    def _query_profile_for_search_terms(self, search_terms, expected_result):
        """Query the profile matching the given search terms and checks that it returns
        the expected result."""

        # Get a signed body.
        signed_search_request = signedjson.sign.sign_json(
            {"search_term": search_terms}, "fake.server", self.signing_key,
        )

        # Send the request.
        request, channel = make_request(
            self.sydent.reactor,
            "POST",
            "/_matrix/identity/api/v1/user_directory/search",
            json.dumps(signed_search_request),
        )
        request.render(self.sydent.servlets.userDirectorySearchServlet)

        self.assertEqual(channel.code, 200, channel.json_body)

        # Check if the response matches the expected result.
        results = channel.json_body["results"]
        if expected_result is None:
            self.assertEqual(len(channel.json_body["results"]), 0)
        else:
            self.assertEqual(len(channel.json_body["results"]), 1)
            self.assertDictContainsSubset(expected_result, results[0])

