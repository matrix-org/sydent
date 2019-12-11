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

from sydent.replication.peer import RemotePeer


class PeerStore:
    def __init__(self, sydent):
        self.sydent = sydent

    def getPeerByName(self, name):
        cur = self.sydent.db.cursor()
        res = cur.execute("select p.name, p.port, "
                          "p.lastSentAssocsId, p.lastSentInviteTokensId, p.lastSentInviteUpdatesId, p.lastSentEphemeralKeysId, "
                          "p.shadow, pk.alg, pk.key from peers p, peer_pubkeys pk "
                          "where p.name = ? and pk.peername = p.name and p.active = 1", (name,))

        serverName = None
        port = None
        lastSentAssocsId = None
        lastSentInviteTokensId = None
        lastSentInviteUpdatesId = None
        lastSentEphemeralKeysId = None
        pubkeys = {}

        for row in res.fetchall():
            serverName = row[0]
            port = row[1]
            lastSentAssocsId = row[2]
            lastSentInviteTokensId = row[3]
            lastSentInviteUpdatesId = row[4]
            lastSentEphemeralKeysId = row[5]
            shadow = row[6]
            pubkeys[row[7]] = row[8]

        if len(pubkeys) == 0:
            return None

        p = RemotePeer(self.sydent, serverName, port, pubkeys)
        p.lastSentAssocsId = lastSentAssocsId
        p.lastSentInviteTokensId = lastSentInviteTokensId
        p.lastSentInviteUpdatesId = lastSentInviteUpdatesId
        p.lastSentEphemeralKeysId = lastSentEphemeralKeysId
        p.shadow = True if shadow else False

        return p

    def getAllPeers(self):
        cur = self.sydent.db.cursor()
        res = cur.execute("select p.name, p.port, "
                          "p.lastSentAssocsId, p.lastSentInviteTokensId, p.lastSentEphemeralKeysId, "
                          "p.shadow, pk.alg, pk.key from peers p, peer_pubkeys pk "
                          "where pk.peername = p.name and p.active = 1")

        peers = []

        peername = None
        port = None
        lastSentAssocsId = 0
        lastSentInviteTokensId = 0
        lastSentEphemeralKeysId = 0
        pubkeys = {}

        for row in res.fetchall():
            if row[0] != peername:
                if len(pubkeys) > 0:
                    p = RemotePeer(self.sydent, peername, port, pubkeys)
                    p.lastSentAssocsId = lastSentAssocsId
                    p.lastSentInviteTokensId = lastSentInviteTokensId
                    p.lastSentEphemeralKeysId = lastSentEphemeralKeysId
                    peers.append(p)
                    pubkeys = {}
                peername = row[0]
                port = row[1]
                lastSentAssocsId = row[2]
                lastSentInviteTokensId = row[3]
                lastSentEphemeralKeysId = row[4]
                shadow = row[5]
            pubkeys[row[6]] = row[7]

        if len(pubkeys) > 0:
            p = RemotePeer(self.sydent, peername, port, pubkeys)
            p.lastSentAssocsId = lastSentAssocsId
            p.lastSentInviteTokensId = lastSentInviteTokensId
            p.lastSentEphemeralKeysId = lastSentEphemeralKeysId
            p.shadow = True if shadow else False
            peers.append(p)
            pubkeys = {}

        return peers

    def setLastSentIdAndPokeSucceeded(self, peerName, ids, lastPokeSucceeded):
        """Set last successful replication of data to this peer.

        If an id for a replicated database table is None, the last sent value
        will not be updated.

        :param peerName: The name of the peer.
        :type peerName: str
        :param ids: A Dictionary of ids that represent the last database
            table ids that were replicated to this peer.
        :type ids: Dict[str, int]
        :param lastPokeSucceeded: The time of when the last successful
            replication succeeded (even if no actual replication of data was
            necessary).
        :type lastPokeSucceeded: int
        """

        cur = self.sydent.db.cursor()
        if ids["sg_assocs"]:
            cur.execute("update peers set lastSentAssocsId = ?, lastPokeSucceededAt = ? "
                        "where name = ?", (ids["sg_assocs"], lastPokeSucceeded, peerName))
        if ids["invite_tokens"]:
            cur.execute("update peers set lastSentInviteTokensId = ?, lastPokeSucceededAt = ? "
                        "where name = ?", (ids["invite_tokens"], lastPokeSucceeded, peerName))
        if ids["ephemeral_public_keys"]:
            cur.execute("update peers set lastSentEphemeralKeysId = ?, lastPokeSucceededAt = ? "
                        "where name = ?", (ids["ephemeral_public_keys"], lastPokeSucceeded, peerName))
        self.sydent.db.commit()
