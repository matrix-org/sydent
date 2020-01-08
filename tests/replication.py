from twisted.trial import unittest
from . import make_sydent
from sydent.replication.peer import RemotePeer
from mock import MagicMock
from sydent.db.threepid_associations import LocalAssociationStore
from sydent.threepid import ThreepidAssociation
from sydent.threepid.signer import Signer
from sydent.db.peers import PeerStore


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
        peer_pubkeys = {"ed25519": peer_public_key_base64}
        peer = RemotePeer(sydent, "fake.server", 1234, peer_pubkeys)
        peer.lastSentVersion = 0

        # Replace sydent's PeerStore to inject our fake peer
        peer_store = PeerStore(sydent)
        peer_store.getAllPeers = MagicMock(return_value=[peer])
        sydent.pusher.peerStore = peer_store

        # Mock a local association store to create fake associations
        mocked_assoc_store = LocalAssociationStore(sydent)

        assocs = {}
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
            assocs[i] = assoc
        mocked_assoc_store.getAssociationsAfterId = MagicMock(
            return_value=(assocs, assoc_count)
        )
        sydent.pusher.local_assoc_store = mocked_assoc_store

        # Sign the association payload and assume the one sydent will produce with match
        signer = Signer(sydent)
        signed_assocs = {}
        for assoc_id, assoc in assocs.items():
            signed_assoc = signer.signedThreePidAssociation(assoc)
            signed_assocs[assoc_id] = signed_assoc

        # Mock the pushUpdates method
        result = MagicMock(spec=["code", "phrase"])
        result.code = 200
        result.phrase = "OK"
        peer.pushUpdates = MagicMock(return_value=result)

        # Start sydent and wait for an automated peer push
        sydent.run()
        sydent.reactor.advance(1000)

        # Ensure a push occurred with the correct data
        peer.pushUpdates.assert_called_with(signed_assocs)
