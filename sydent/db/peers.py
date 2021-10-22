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

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from sydent.replication.peer import RemotePeer

if TYPE_CHECKING:
    from sydent.sydent import Sydent


class PeerStore:
    def __init__(self, sydent: "Sydent") -> None:
        self.sydent = sydent

    def getPeerByName(self, name: str) -> Optional[RemotePeer]:
        """
        Retrieves a remote peer using it's server name.

        :param name: The server name of the peer.

        :return: The retrieved peer.
        """
        cur = self.sydent.db.cursor()
        res = cur.execute(
            "select p.name, p.port, p.lastSentVersion, pk.alg, pk.key from peers p, peer_pubkeys pk "
            "where p.name = ? and pk.peername = p.name and p.active = 1",
            (name,),
        )

        # Type safety: if the query returns no rows, pubkeys will be empty
        # and we'll return None before using serverName. Otherwise, we'll read
        # at least one row and assign serverName a string value, because the
        # `name` column is declared `not null` in the DB.
        serverName: str = None  # type: ignore[assignment]
        port: Optional[int] = None
        lastSentVer: Optional[int] = None
        pubkeys: Dict[str, str] = {}

        row: Tuple[str, Optional[int], Optional[int], str, str]
        for row in res.fetchall():
            serverName = row[0]
            port = row[1]
            lastSentVer = row[2]
            pubkeys[row[3]] = row[4]

        if len(pubkeys) == 0:
            return None

        p = RemotePeer(self.sydent, serverName, port, pubkeys, lastSentVer)

        return p

    def getAllPeers(self) -> List[RemotePeer]:
        """
        Retrieve all of the remote peers from the database.

        :return: A list of the remote peers this server knows about.
        """
        cur = self.sydent.db.cursor()
        res = cur.execute(
            "select p.name, p.port, p.lastSentVersion, pk.alg, pk.key from peers p, peer_pubkeys pk "
            "where pk.peername = p.name and p.active = 1"
        )

        peers = []

        # Safety: we need to convince ourselves that `peername` will be not None
        # when passed to `RemotePeer`.
        #
        # If `res` is empty, then `pubkeys` will start empty and never be written to.
        # So we will never create a `RemotePeer`. That's fine.
        #
        # Otherwise we process at least one row. The first row we process will
        # satisfy `row[0] is not None` because `name` is nonnull in the schema.
        # `pubkeys` will be empty, so we skip the innermost `if` and assign peername
        # to be a string. There are no further assignments of `None` to `peername`;
        # it will be a string whenever we use it.
        peername: str = None  # type: ignore[assignment]
        port = None
        lastSentVer = None
        pubkeys: Dict[str, str] = {}

        row: Tuple[str, Optional[int], Optional[int], str, str]
        for row in res.fetchall():
            if row[0] != peername:
                if len(pubkeys) > 0:
                    p = RemotePeer(self.sydent, peername, port, pubkeys, lastSentVer)
                    peers.append(p)
                    pubkeys = {}
                peername = row[0]
                port = row[1]
                lastSentVer = row[2]
            pubkeys[row[3]] = row[4]

        if len(pubkeys) > 0:
            p = RemotePeer(self.sydent, peername, port, pubkeys, lastSentVer)
            peers.append(p)

        return peers

    def setLastSentVersionAndPokeSucceeded(
        self,
        peerName: str,
        lastSentVersion: Optional[int],
        lastPokeSucceeded: Optional[int],
    ) -> None:
        """
        Sets the ID of the last association sent to a given peer and the time of the
        last successful request sent to that peer.

        :param peerName: The server name of the peer.
        :param lastSentVersion: The ID of the last association sent to that peer.
        :param lastPokeSucceeded: The timestamp in milliseconds of the last successful
            request sent to that peer.
        """
        cur = self.sydent.db.cursor()
        cur.execute(
            "update peers set lastSentVersion = ?, lastPokeSucceededAt = ? "
            "where name = ?",
            (lastSentVersion, lastPokeSucceeded, peerName),
        )
        self.sydent.db.commit()
