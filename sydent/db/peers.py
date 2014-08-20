# -*- coding: utf-8 -*-

# Copyright 2014 matrix.org
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
        res = cur.execute("select p.name, p.lastSentVersion, pk.alg, pk.key from peers p, peer_pubkeys pk where "
                          "p.name = ? and pk.peername = p.name and p.active = 1", (name,))

        pubkeys = {}

        for row in res.fetchall():
            lastSentVer = row[1]
            pubkeys[row[2]] = row[3]

        if len(pubkeys) == 0:
            return None

        p = RemotePeer(name, pubkeys)
        p.lastSentVersion = lastSentVer

        return p

    def getAllPeers(self):
        cur = self.sydent.db.cursor()
        res = cur.execute("select p.name, p.lastSentVersion, pk.alg, pk.key from peers p, peer_pubkeys pk where "
                          "pk.peername = p.name and p.active = 1")

        peers = []

        peername = None
        lastSentVer = None
        pubkeys = {}

        for row in res.fetchall():
            if row[0] != peername:
                if len(pubkeys) > 0:
                    peers.append(RemotePeer(peername, pubkeys))
                    pubkeys = {}
                peername = row[0]
                lastSentVer = row[1]
            pubkeys[row[2]] = row[3]

        if len(pubkeys) > 0:
            p = RemotePeer(peername, pubkeys)
            p.lastSentVersion = lastSentVer
            peers.append(p)
            pubkeys = {}

        return peers

    def setLastPokeSucceeded(self, peerName, lastPokeSucceeded):
        cur = self.sydent.db.cursor()
        res = cur.execute("update peers set lastPokeSucceeded = ? where name = ?", (lastPokeSucceeded, peerName))
        self.sydent.db.commit()