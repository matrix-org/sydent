from twisted.trial import unittest
from . import make_sydent
from sydent.replication.peer import RemotePeer
from mock import MagicMock
from sydent.db.threepid_associations import LocalAssociationStore
from sydent.threepid import ThreepidAssociation
from sydent.threepid.signer import Signer
from sydent.db.peers import PeerStore
from sydent.http.httpsclient import ReplicationHttpsClient
from twisted.internet.defer import Deferred


class ReplicationTestCase(unittest.TestCase):
    """Test that a sydent can correctly replicate data to another sydent"""

    def test_pushing_to_peer(self):
        """Sydent has a background job that runs every 10s in order to push new
        associations to peers. These peers are defined in sydent's db

        Make a fake peer and associations and make sure Sydent tries to push to it.
        """
        # Create a new sydent
        config = {
            "crypto": {
                "ed25519.signingkey": "ed25519 0 FJi1Rnpj3/otydngacrwddFvwz/dTDsBv62uZDN2fZM"
            }
        }
        sydent = make_sydent(test_config=config)

        # Create fake peer to replicate to
        peer_public_key_base64 = "t6PBLcDIx0irB1JbcBEiuIvXj2AMdjQtJ/JeX5JETN4"

        # Inject our fake peer into the database
        cur = sydent.db.cursor()
        cur.execute(
            "insert into peers (name, port, lastSentVersion) VALUES (?, ?, ?)",
            ("fake.server", 1234, 0)
        )
        cur.execute(
            "insert into peer_pubkeys (peername, alg, key) VALUES (?, ?, ?)",
            ("fake.server", "ed25519", peer_public_key_base64)
        )

        # Insert fake associations into the db
        assocs = []
        assoc_count = 150
        for i in range(assoc_count):
            assoc = {
                "email",
                "bob%d@example.com" % i,
                None,
                "@bob%d:example.com" % i,
                i * 10000,
                0,
                99999999999,
            }
            assocs.append(assoc)
        cur.executemany(
            "insert into local_threepid_associations "
            "(medium, address, mxid, ts, notBefore, notAfter) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            assocs
        )

        sydent.db.commit()

        # Manually sign all associations and ensure sydent attempted to push the same
        signer = Signer(sydent)
        signed_assocs = {}
        for assoc_id, assoc in enumerate(assocs):
            signed_assoc = signer.signedThreePidAssociation(assoc)
            signed_assocs[assoc_id] = signed_assoc

        agent = MagicMock()

        # Start sydent and wait for an automated peer push
        sydent.run()
        sydent.reactor.advance(1000)

        # Ensure a push occurred with the correct data
        replication_url = "https://fake.server:1234/_matrix/identity/replicate/v1/push"
        sydent.replicationHttpsClient.postJson.assert_called_with(
            replication_url, signed_assocs
        )
