# -*- coding: utf-8 -*-

# Copyright 2014 OpenMarket Ltd
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
import copy

import twisted.internet.reactor
import twisted.internet.task

from sydent.util import time_msec
from sydent.replication.peer import LocalPeer
from sydent.db.threepid_associations import LocalAssociationStore
from sydent.db.invite_tokens import JoinTokenStore
from sydent.db.peers import PeerStore
from sydent.threepid.signer import Signer

logger = logging.getLogger(__name__)

EPHEMERAL_PUBLIC_KEYS_PUSH_LIMIT = 100
INVITE_TOKENS_PUSH_LIMIT = 100
ASSOCIATIONS_PUSH_LIMIT = 100

class Pusher:
    def __init__(self, sydent):
        self.sydent = sydent
        self.pushing = False
        self.peerStore = PeerStore(self.sydent)

    def setup(self):
        cb = twisted.internet.task.LoopingCall(Pusher.scheduledPush, self)
        cb.start(10.0)

    def getSignedAssociationsAfterId(self, afterId, limit, shadow=False):
        """Return max `limit` associations from the database after a given
        DB table id.

        :param afterId: A database id to act as an offset. Rows after this id
            are returned.
        :type afterId: int
        :param limit: Max amount of database rows to return.
        :type limit: int
        :param shadow: Whether these associations are intended for a shadow
            server.
        :type shadow: bool
        :returns a tuple with the first item being a dict of associations,
            and the second being the maximum table id of the returned
            associations.
        :rtype: Tuple[Dict[Dict, Dict], int|None]
        """
        assocs = {}

        localAssocStore = LocalAssociationStore(self.sydent)
        (localAssocs, maxId) = localAssocStore.getAssociationsAfterId(afterId, limit)

        signer = Signer(self.sydent)

        for localId, assoc in localAssocs.items():
            if shadow and self.sydent.shadow_hs_master and self.sydent.shadow_hs_slave:
                # mxid is null if 3pid has been unbound
                if assoc.mxid:
                    assoc.mxid = assoc.mxid.replace(
                        ":" + self.sydent.shadow_hs_master,
                        ":" + self.sydent.shadow_hs_slave
                    )

            assocs[localId] = signer.signedThreePidAssociation(assoc)

        return (assocs, maxId)

    def doLocalPush(self):
        """
        Synchronously push local associations to this server (ie. copy them to globals table)
        The local server is essentially treated the same as any other peer except we don't do the
        network round-trip and this function can be used so the association goes into the global table
        before the http call returns (so clients know it will be available on at least the same ID server they used)
        """
        localPeer = LocalPeer(self.sydent)

        (signedAssocs, _) = self.getSignedAssociationsAfterId(localPeer.lastId, None)

        localPeer.pushUpdates(signedAssocs)

    def scheduledPush(self):
        """Push pending updates to a remote peer. To be called regularly."""
        if self.pushing:
            return
        self.pushing = True

        join_token_store = JoinTokenStore(self.sydent)

        try:
            peers = self.peerStore.getAllPeers()

            for p in peers:
                logger.debug("Looking for updates to push to %s", p.servername)

                # Dictionary for holding all data to push
                push_data = {}

                # Dictionary for holding all the ids of db tables we've successfully replicated up to
                ids = {}
                total_updates = 0

                # Push associations
                (push_data["sg_assocs"], ids["sg_assocs"]) = self.getSignedAssociationsAfterId(p.lastSentAssocsId, ASSOCIATIONS_PUSH_LIMIT, p.shadow)
                total_updates += len(push_data["sg_assocs"])

                # Push invite tokens and ephemeral public keys
                (push_data["invite_tokens"], ids["invite_tokens"]) = join_token_store.getInviteTokensAfterId(p.lastSentInviteTokensId, INVITE_TOKENS_PUSH_LIMIT)
                (push_data["ephemeral_public_keys"], ids["ephemeral_public_keys"]) = join_token_store.getEphemeralPublicKeysAfterId(p.lastSentEphemeralKeysId, EPHEMERAL_PUBLIC_KEYS_PUSH_LIMIT)
                total_updates += len(push_data["invite_tokens"]) + len(push_data["ephemeral_public_keys"])

                logger.debug("%d updates to push to %s", total_updates, p.servername)
                if total_updates:
                    logger.info("Pushing %d updates to %s:%d", total_updates, p.servername, p.port)
                    try:
                        updateDeferred = p.pushUpdates(push_data)
                        updateDeferred.addCallback(self._pushSucceeded, peer=p, ids=ids)
                        updateDeferred.addErrback(self._pushFailed, peer=p)
                    except Exception as e:
                        logger.exception("Error pushing updates to %s", p.servername)
        finally:
            self.pushing = False

    def _pushSucceeded(self, result, peer, ids):
        """To be called after a successful push to a remote peer."""
        logger.info("Pushed updates to %s with result %d %s",
                    peer.servername, result.code, result.phrase)

        self.peerStore.setLastSentIdAndPokeSucceeded(peer.servername, ids, time_msec())

    def _pushFailed(self, failure, peer):
        """To be called after an unsuccessful push to a remote peer."""
        logger.info("Failed to push updates to %s:%s: %s", peer.servername, peer.port, failure)
