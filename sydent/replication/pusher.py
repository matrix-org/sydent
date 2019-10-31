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

import logging

from twisted.internet import defer
import twisted.internet.reactor
import twisted.internet.task

from sydent.util import time_msec
from sydent.replication.peer import LocalPeer
from sydent.db.invite_tokens import JoinTokenStore
from sydent.db.threepid_associations import LocalAssociationStore
from sydent.db.peers import PeerStore

logger = logging.getLogger(__name__)

EPHEMERAL_PUBLIC_KEYS_PUSH_LIMIT = 100
INVITE_TOKENS_PUSH_LIMIT = 100
ASSOCIATIONS_PUSH_LIMIT = 100


class Pusher:
    def __init__(self, sydent):
        self.sydent = sydent
        self.pushing = False
        self.peerStore = PeerStore(self.sydent)
        self.join_token_store = JoinTokenStore(self.sydent)
        self.local_assoc_store = LocalAssociationStore(self.sydent)

    def setup(self):
        cb = twisted.internet.task.LoopingCall(Pusher.scheduledPush, self)
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
        """Push pending updates to a remote peer. To be called regularly.

        :returns a deferred.DeferredList of defers, one per peer we're pushing to that will
        resolve when pushing to that peer has completed, successfully or otherwise
        :rtype deferred.DeferredList
        """
        peers = self.peerStore.getAllPeers()

        # Push to all peers in parallel
        return defer.DeferredList([self._push_to_peer(p) for p in peers])

    @defer.inlineCallbacks
    def _push_to_peer(self, p):
        logger.debug("Looking for updates to push to %s", p.servername)

        # Check if a push operation is already active. If so, don't start another
        if p.is_being_pushed_to:
            logger.debug("Waiting for %s:%d to finish pushing...", p.servername, p.port)
            return

        p.is_being_pushed_to = True

        try:
            # Keep looping until we're sure that there's no updates left to send
            while True:
                # Dictionary for holding all data to push
                push_data = {}

                # Dictionary for holding all the ids of db tables we've successfully replicated
                ids = {}
                total_updates = 0

                # Push associations
                associations = self.local_assoc_store.getSignedAssociationsAfterId(
                    p.lastSentAssocsId, ASSOCIATIONS_PUSH_LIMIT
                )
                push_data["sg_assocs"], ids["sg_assocs"] = associations

                # Push invite tokens and ephemeral public keys
                tokens = self.join_token_store.getInviteTokensAfterId(
                    p.lastSentInviteTokensId, INVITE_TOKENS_PUSH_LIMIT
                )
                push_data["invite_tokens"], ids["invite_tokens"] = tokens

                keys = self.join_token_store.getEphemeralPublicKeysAfterId(
                    p.lastSentEphemeralKeysId, EPHEMERAL_PUBLIC_KEYS_PUSH_LIMIT
                )
                push_data["ephemeral_public_keys"], ids["ephemeral_public_keys"] = keys

                token_count = len(push_data["invite_tokens"])
                key_count = len(push_data["ephemeral_public_keys"])
                association_count = len(push_data["sg_assocs"])

                total_updates += token_count + key_count + association_count

                logger.debug(
                    "%d updates to push to %s:%d",
                    total_updates, p.servername, p.port
                )

                # If there are no updates left to send, break the loop
                if not total_updates:
                    logger.info("Pushing updates to %s:%d finished", p.servername, p.port)
                    break

                logger.info("Pushing %d updates to %s:%d", total_updates, p.servername, p.port)
                result = yield p.pushUpdates(push_data)

                logger.info(
                    "Pushed updates to %s:%d with result %d %s",
                    p.servername, p.port, result.code, result.phrase
                )

                yield self.peerStore.setLastSentIdAndPokeSucceeded(
                    p.servername, ids, time_msec()
                )
        except Exception:
            logger.exception("Error pushing updates to %s:%d: %r", p.servername, p.port)
        finally:
            # Whether pushing completed or an error occurred, signal that pushing has finished
            p.is_being_pushed_to = False
