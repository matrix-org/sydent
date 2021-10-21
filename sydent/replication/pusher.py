# Copyright 2014 OpenMarket Ltd
# Copyright 2019 The Matrix.org Foundation C.I.C.
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

import logging
from typing import TYPE_CHECKING, List, Tuple

import twisted.internet.reactor
import twisted.internet.task
from twisted.internet import defer

from sydent.db.peers import PeerStore
from sydent.db.threepid_associations import LocalAssociationStore
from sydent.replication.peer import LocalPeer, RemotePeer
from sydent.util import time_msec

if TYPE_CHECKING:
    from sydent.sydent import Sydent

logger = logging.getLogger(__name__)

# Maximum amount of signed associations to replicate to a peer at a time
ASSOCIATIONS_PUSH_LIMIT = 100


class Pusher:
    def __init__(self, sydent: "Sydent") -> None:
        self.sydent = sydent
        self.pushing = False
        self.peerStore = PeerStore(self.sydent)
        self.local_assoc_store = LocalAssociationStore(self.sydent)

    def setup(self) -> None:
        cb = twisted.internet.task.LoopingCall(Pusher.scheduledPush, self)
        cb.clock = self.sydent.reactor
        cb.start(10.0)

    def doLocalPush(self) -> None:
        """
        Synchronously push local associations to this server (ie. copy them to globals table)
        The local server is essentially treated the same as any other peer except we don't do
        the network round-trip and this function can be used so the association goes into the
        global table before the http call returns (so clients know it will be available on at
        least the same ID server they used)
        """
        localPeer = LocalPeer(self.sydent)

        signedAssocs, _ = self.local_assoc_store.getSignedAssociationsAfterId(
            localPeer.lastId, None
        )

        localPeer.pushUpdates(signedAssocs)

    def scheduledPush(self) -> "defer.Deferred[List[Tuple[bool, None]]]":
        """Push pending updates to all known remote peers. To be called regularly.

        :returns a deferred.DeferredList of defers, one per peer we're pushing to that will
        resolve when pushing to that peer has completed, successfully or otherwise
        """
        peers = self.peerStore.getAllPeers()

        # Push to all peers in parallel
        dl = []
        for p in peers:
            dl.append(defer.ensureDeferred(self._push_to_peer(p)))
        return defer.DeferredList(dl)

    async def _push_to_peer(self, p: "RemotePeer") -> None:
        """
        For a given peer, retrieves the list of associations that were created since
        the last successful push to this peer (limited to ASSOCIATIONS_PUSH_LIMIT) and
        sends them.

        :param p: The peer to send associations to.
        """
        logger.debug("Looking for updates to push to %s", p.servername)

        # Check if a push operation is already active. If so, don't start another
        if p.is_being_pushed_to:
            logger.debug(
                "Waiting for %s to finish pushing...", p.replication_url_origin
            )
            return

        p.is_being_pushed_to = True

        try:
            # Push associations
            (
                assocs,
                latest_assoc_id,
            ) = self.local_assoc_store.getSignedAssociationsAfterId(
                p.lastSentVersion, ASSOCIATIONS_PUSH_LIMIT
            )

            # If there are no updates left to send, break the loop
            if not assocs:
                return

            logger.info(
                "Pushing %d updates to %s", len(assocs), p.replication_url_origin
            )
            result = await p.pushUpdates(assocs)

            self.peerStore.setLastSentVersionAndPokeSucceeded(
                p.servername, latest_assoc_id, time_msec()
            )

            logger.info(
                "Pushed updates to %s with result %d %s",
                p.replication_url_origin,
                result.code,
                result.phrase,
            )
        except Exception:
            logger.exception("Error pushing updates to %s", p.replication_url_origin)
        finally:
            # Whether pushing completed or an error occurred, signal that pushing has finished
            p.is_being_pushed_to = False
