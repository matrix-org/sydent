import json

from twisted.web.client import Response
from twisted.internet import defer
from twisted.trial import unittest
from tests.utils import make_request, make_sydent
from mock import Mock
from sydent.threepid import ThreepidAssociation
from sydent.threepid.signer import Signer


class ReplicationTestCase(unittest.TestCase):
    """Test that a sydent can correctly replicate data to another sydent"""

    def setUp(self):
        # Create a new sydent
        config = {
            "crypto": {
                "ed25519.signingkey": "ed25519 0 FJi1Rnpj3/otydngacrwddFvwz/dTDsBv62uZDN2fZM"
            }
        }
        self.sydent = make_sydent(test_config=config)

        # Create fake peer to replicate to
        peer_public_key_base64 = "+vB8mTaooD/MA8YYZM8t9+vnGhP1937q2icrqPV9JTs"

        # Inject our fake peer into the database
        cur = self.sydent.db.cursor()
        cur.execute(
            "insert into peers (name, port, lastSentVersion, active) VALUES (?, ?, ?, ?)",
            ("fake.server", 1234, 0, 1)
        )
        cur.execute(
            "insert into peer_pubkeys (peername, alg, key) VALUES (?, ?, ?)",
            ("fake.server", "ed25519", peer_public_key_base64)
        )

        self.sydent.db.commit()

        # Insert fake associations into the db
        self.assocs = []
        assoc_count = 150
        for i in range(assoc_count):
            assoc = ThreepidAssociation(
                medium="email",
                address="bob%d@example.com" % i,
                lookup_hash=None,
                mxid="@bob%d:example.com" % i,
                ts=(i * 10000),
                not_before=0,
                not_after=99999999999,
            )
            self.assocs.append(assoc)

    def test_incoming_replication(self):
        """Impersonate a peer that sends a replication push to Sydent, then checks that it
        accepts the payload and saves it correctly.
        """
        self.sydent.run()

        config = {
            "general": {
                "server.name": "fake.server"
            },
            "crypto": {
                "ed25519.signingkey": "ed25519 0 b29eXMMAYCFvFEtq9mLI42aivMtcg4Hl0wK89a+Vb6c"
            }
        }

        fake_sydent = make_sydent(config)
        signer = Signer(fake_sydent)

        signed_assocs = {}
        for assoc_id, assoc in enumerate(self.assocs):
            signed_assoc = signer.signedThreePidAssociation(assoc)
            signed_assocs[assoc_id] = signed_assoc

        body = json.dumps({"sgAssocs": signed_assocs})
        request, channel = make_request(
            self.sydent.reactor, "POST", "/_matrix/identity/replicate/v1/push", body
        )
        request.render(self.sydent.servlets.replicationPush)

        self.assertEqual(channel.code, 200)

        cur = self.sydent.db.cursor()
        res = cur.execute("SELECT originId, sgAssoc FROM global_threepid_associations")

        for row in res.fetchall():
            originId = row[0]
            signed_assoc = json.loads(row[1])

            self.assertDictEqual(signed_assoc, signed_assocs[originId])

    def test_outgoing_replication(self):
        """Sydent has a background job that runs every 10s in order to push new
        associations to peers. These peers are defined in sydent's db

        Make a fake peer and associations and make sure Sydent tries to push to it.
        """
        cur = self.sydent.db.cursor()

        cur.executemany(
            "insert into local_threepid_associations "
            "(medium, address, lookup_hash, mxid, ts, notBefore, notAfter) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    assoc.medium,
                    assoc.address,
                    assoc.lookup_hash,
                    assoc.mxid, assoc.ts,
                    assoc.not_before,
                    assoc.not_after,
                )
                for assoc in self.assocs
            ]
        )

        self.sydent.db.commit()

        # Manually sign all associations and ensure sydent attempted to push the same
        signer = Signer(self.sydent)
        signed_assocs = {}
        for assoc_id, assoc in enumerate(self.assocs):
            signed_assoc = signer.signedThreePidAssociation(assoc)
            signed_assocs[assoc_id] = signed_assoc

        sent_assocs = {}

        def request(method, uri, headers, body):
            # Check the method and the URI.
            assert method == 'POST'
            assert uri == 'https://fake.server:1234/_matrix/identity/replicate/v1/push'

            # postJson calls the agent with a StringIO within a FileBodyProducer.
            payload = json.loads(body._inputFile.buf)
            for assoc_id, assoc in payload['sgAssocs'].items():
                sent_assocs[assoc_id] = assoc

            # Return with a fake response wrapped in a deferred.
            d = defer.Deferred()
            d.callback(Response((b'HTTP', 1, 1), 200, b'OK', None, None))
            return d

        agent = Mock(spec=['request'])
        agent.request.side_effect = request
        self.sydent.replicationHttpsClient.agent = agent

        # Start sydent and wait for an automated peer push
        self.sydent.run()
        self.sydent.reactor.advance(1000)

        # Ensure at least one push occurred with the correct data
        self.assertEqual(len(self.assocs), len(sent_assocs))
        for assoc_id, assoc in sent_assocs.items():
            self.assertDictEqual(assoc, signed_assocs[int(assoc_id)-1])
