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

import twisted.internet.reactor
import twisted.internet.task

from sydent.util import time_msec
from sydent.replication.peer import LocalPeer
from sydent.db.threepid_associations import LocalAssociationStore
from sydent.db.invite_tokens import JoinTokenStore
from sydent.db.peers import PeerStore
from sydent.threepid.assocsigner import AssociationSigner

logger = logging.getLogger(__name__)

EPHEMERAL_KEYS_PUSH_LIMIT = 100
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

    def getSignedAssociationsAfterId(self, afterId, limit):
        signedAssocs = {}

        localAssocStore = LocalAssociationStore(self.sydent)
        (localAssocs, maxId) = localAssocStore.getAssociationsAfterId(afterId, limit)

        assocSigner = AssociationSigner(self.sydent)

        for localId in localAssocs:
            sgAssoc = assocSigner.signedThreePidAssociation(localAssocs[localId])
            shadowSgAssoc = None

            if self.sydent.shadow_hs_master and self.sydent.shadow_hs_slave:
                shadowAssoc = copy.deepcopy(localAssocs[localId])
                shadowAssoc.mxid = shadowAssoc.mxid.replace(
                    ":" + self.sydent.shadow_hs_master,
                    ":" + self.sydent.shadow_hs_slave
                )
                shadowSgAssoc = assocSigner.signedThreePidAssociation(shadowAssoc)

            signedAssocs[localId] = (sgAssoc, shadowSgAssoc)

        return (signedAssocs, maxId)

    def getInviteTokensAfterId(self, afterId, limit):
        join_token_store = JoinTokenStore(self.sydent)
        (invite_tokens, maxId) = join_token_store.getTokensAfterId(afterId, limit)

        # TODO: Do something for shadow servers?

        return (invite_tokens, maxId)

    def getEphemeralKeysAfterId(self, afterId, limit):
        join_token_store = JoinTokenStore(self.sydent)
        (ephemeral_keys, maxId) = join_token_store.getEphemeralPublicKeysAfterId(afterId, limit)

        # TODO: Do something for shadow servers?

        return (ephemeral_keys, maxId)

    def doLocalPush(self):
        """
        Synchronously push local associations to this server (ie. copy them to globals table)
        The local server is essentially treated the same as any other peer except we don't do the
        network round-trip and this function can be used so the association goes into the global table
        before the http call returns (so clients know it will be available on at least the same ID server they used)
        """
        localPeer = LocalPeer(self.sydent)

        signedAssocs = self.getSignedAssociationsAfterId(localPeer.lastId, None)[0]

        localPeer.pushUpdates(signedAssocs)

    def scheduledPush(self):
        if self.pushing:
            return
        self.pushing = True

        updateDeferred = None

        try:
            peers = self.peerStore.getAllPeers()

            for p in peers:
                logger.debug("Looking for updates to push to %s", p.servername)

                # Dictionary for holding all data to push
                push_data = {}
                ids = {}
                total_updates = 0

                (push_data["sg_assocs"], ids["sg_assocs"]) = self.getSignedAssociationsAfterId(p.lastSentAssocsId, ASSOCIATIONS_PUSH_LIMIT)
                total_updates += len(push_data["sg_assocs"])

                if True: # TODO: Require a specific flag for invite replication
                    (push_data["invite_tokens"], ids["invite_tokens"]) = self.getInviteTokensAfterId(p.lastSentInviteTokensId, INVITE_TOKENS_PUSH_LIMIT)
                    (push_data["ephemeral_keys"], ids["ephemeral_keys"]) = self.getEphemeralKeysAfterId(p.lastSentEphemeralKeysId, EPHEMERAL_KEYS_PUSH_LIMIT)
                    total_updates += len(push_data["invite_tokens"]) + len(push_data["ephemeral_keys"])

                logger.debug("%d updates to push to %s", total_updates, p.servername)
                if total_updates:
                    logger.info("Pushing %d updates to %s", total_updates, p.servername)
                    logger.info("Sending: %s", str(push_data))
                    updateDeferred = p.pushUpdates(push_data)
                    updateDeferred.addCallback(self._pushSucceeded, peer=p, ids=ids)
                    updateDeferred.addErrback(self._pushFailed, peer=p)
                    break
        finally:
            if not updateDeferred:
                self.pushing = False

    def _pushSucceeded(self, result, peer, ids):
        logger.info("Pushed updates to %s with result %d %s",
                    peer.servername, result.code, result.phrase)

        self.peerStore.setLastSentIdAndPokeSucceeded(peer.servername, ids, time_msec())

        self.pushing = False
        self.scheduledPush()

    def _pushFailed(self, failure, peer):
        logger.info("Failed to push updates to %s:%s: %s", peer.servername, peer.port, failure)
        self.pushing = False
        return None
