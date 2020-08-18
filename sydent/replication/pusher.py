# -*- coding: utf-8 -*-

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
from __future__ import absolute_import

import logging

from twisted.internet import defer
import twisted.internet.reactor
import twisted.internet.task

from sydent.util import time_msec
from sydent.replication.peer import LocalPeer
from sydent.db.threepid_associations import LocalAssociationStore
from sydent.db.invite_tokens import JoinTokenStore
from sydent.db.peers import PeerStore

logger = logging.getLogger(__name__)

# Maximum amount of signed objects to replicate to a peer at a time
EPHEMERAL_PUBLIC_KEYS_PUSH_LIMIT = 100
INVITE_TOKENS_PUSH_LIMIT = 100
INVITE_UPDATES_PUSH_LIMIT = 100
ASSOCIATIONS_PUSH_LIMIT = 100

# Amount of seconds before we'll timeout pushing to a single peer
# Other peers will wait on this timeout before another round of pushes is triggered
PUSH_TIMEOUT_S = 60


class Pusher:
    def __init__(self, sydent):
        self.sydent = sydent
        self.pushing = False
        self.peerStore = PeerStore(self.sydent)
        self.join_token_store = JoinTokenStore(self.sydent)
        self.local_assoc_store = LocalAssociationStore(self.sydent)

    def setup(self):
        cb = twisted.internet.task.LoopingCall(Pusher.scheduledPush, self)
        cb.clock = self.sydent.reactor
        cb.start(10.0)

    def doLocalPush(self):
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

    def scheduledPush(self):
        """Push pending updates to all known remote peers. To be called regularly.

        :returns a deferred.DeferredList of defers, one per peer we're pushing to that will
        resolve when pushing to that peer has completed, successfully or otherwise
        :rtype deferred.DeferredList
        """
        peers = self.peerStore.getAllPeers()

        # Push to all peers in parallel
        deferreds = [self._push_to_peer(p) for p in peers]

        # Add timeout to each push
        deferreds = [d.addTimeout(PUSH_TIMEOUT_S, twisted.internet.reactor) for d in deferreds]

        return defer.DeferredList(deferreds)

    @defer.inlineCallbacks
    def _push_to_peer(self, p):
        """
        For a given peer, retrieves the list of associations that were created since
        the last successful push to this peer (limited to ASSOCIATIONS_PUSH_LIMIT) and
        sends them.

        :param p: The peer to send associations to.
        :type p: sydent.replication.peer.RemotePeer
        """
        logger.debug("Looking for updates to push to %s", p.servername)

        # Check if a push operation is already active. If so, don't start another
        if p.is_being_pushed_to:
            logger.debug("Waiting for %s:%d to finish pushing...", p.servername, p.port)
            return

        p.is_being_pushed_to = True

        try:
            # Dictionary for holding all data to push
            push_data = {}

            # Dictionary for holding all the ids of db tables we've successfully replicated
            ids = {}
            total_updates = 0

            # Push associations
            associations, max_id = self.local_assoc_store.getSignedAssociationsAfterId(
                p.lastSentAssocsId, ASSOCIATIONS_PUSH_LIMIT
            )
            push_data["sg_assocs"] = associations
            ids["sg_assocs"] = max_id

            # Push invite tokens and ephemeral public keys
            push_data["invite_tokens"] = {}
            ids["invite_tokens"] = {}

            added, max_id = self.join_token_store.getInviteTokensAfterId(
                p.lastSentInviteTokensId, INVITE_TOKENS_PUSH_LIMIT
            )
            push_data["invite_tokens"]["added"] = added
            ids["invite_tokens"]["added"] = max_id

            updated, max_id = self.join_token_store.getInviteUpdatesAfterId(
                p.lastSentInviteUpdatesId, INVITE_UPDATES_PUSH_LIMIT
            )
            push_data["invite_tokens"]["updated"] = updated
            ids["invite_tokens"]["updated"] = max_id

            keys, max_id = self.join_token_store.getEphemeralPublicKeysAfterId(
                p.lastSentEphemeralKeysId, EPHEMERAL_PUBLIC_KEYS_PUSH_LIMIT
            )
            push_data["ephemeral_public_keys"] = keys
            ids["ephemeral_public_keys"] = max_id

            # Count each of the inner dictionaries instead of the outer
            # (which will always have len 2)
            token_count = (
                len(push_data["invite_tokens"]["added"]) +
                len(push_data["invite_tokens"]["updated"])
            )
            key_count = len(push_data["ephemeral_public_keys"])
            association_count = len(push_data["sg_assocs"])

            total_updates += token_count + key_count + association_count

            logger.debug(
                "%d updates to push to %s:%d",
                total_updates, p.servername, p.port
            )

            # Return if there are no updates to send
            if not total_updates:
                return

            logger.info("Pushing %d updates to %s:%d", total_updates, p.servername, p.port)
            yield p.pushUpdates(push_data)

            yield self.peerStore.setLastSentIdAndPokeSucceeded(
                p.servername, ids, time_msec()
            )

            logger.info(
                "Successfully pushed %d items to %s:%d",
                total_updates, p.servername, p.port
            )
        except Exception:
            logger.exception("Error pushing updates to %s:%d", p.servername, p.port)
        finally:
            # Whether pushing completed or an error occurred, signal that pushing has finished
            p.is_being_pushed_to = False
