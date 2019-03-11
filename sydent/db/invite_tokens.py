# -*- coding: utf-8 -*-

# Copyright 2015 OpenMarket Ltd
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

import time
import logging

logger = logging.getLogger(__name__)

class JoinTokenStore(object):
    def __init__(self, sydent):
        self.sydent = sydent

    def storeToken(self, medium, address, roomId, sender, token, originServer=None, originId=None, commit=True):
        """Stores an invite token.
        
        :param medium: The medium of the token.
        :type medium: str
        :param address: The address of the token.
        :type address: str
        :param roomId: The room ID this token is tied to.
        :type roomId: str
        :param sender: The sender of the invite.
        :type sender: str
        :param token: The token itself.
        :type token: str
        :param originServer: The server this invite originated from (if
            coming from replication).
        :type originServer: str, None
        :param originId: The id of the token in the DB of originServer. Used
        for determining if we've already received a token or not.
        :type originId: int, None
        :param commit: Whether DB changes should be committed by this
            function (or an external one).
        :type commit: bool
        """
        if originId and originServer:
            # Check if we've already seen this association from this server
            last_processed_id = self.getLastTokenIdFromServer(originServer)
            if int(originId) <= int(last_processed_id):
                logger.info("We have already seen token ID %s from %s. Ignoring.", originId, originServer)
                return

        cur = self.sydent.db.cursor()

        cur.execute("INSERT INTO invite_tokens"
                    " ('medium', 'address', 'room_id', 'sender', 'token', 'received_ts', 'origin_server', 'origin_id')"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (medium, address, roomId, sender, token, int(time.time()), originServer, originId))
        if commit:
            self.sydent.db.commit()

    def getTokens(self, medium, address):
        """Retrieve the invite token(s) for a given 3PID medium and address.
        
        :param medium: The medium of the 3PID.
        :type medium: str
        :param address: The address of the 3PID.
        :type address: str
        :returns a list of invite tokens, or an empty list if no tokens found.
        :rtype: list[Dict[str, str]]
        """
        cur = self.sydent.db.cursor()

        res = cur.execute(
            "SELECT medium, address, room_id, sender, token FROM invite_tokens"
            " WHERE medium = ? AND address = ?",
            (medium, address,)
        )
        rows = res.fetchall()

        ret = []

        for row in rows:
            medium, address, roomId, sender, token = row
            ret.append({
                "medium": medium,
                "address": address,
                "room_id": roomId,
                "sender": sender,
                "token": token,
            })

        return ret

    def getInviteTokensAfterId(self, afterId, limit):
        """Retrieves max `limit` invite tokens after a given DB id.
        
        :param afterId: A database id to act as an offset. Tokens after this
            id are returned.
        :type afterId: int
        :param limit: Max amount of database rows to return.
        :type limit: int, None
        :returns a tuple consisting of a dict of invite tokens (with key
            being the token's DB id) and the maximum DB id that was extracted.
            Otherwise returns ({}, None) if no tokens are found.
        :rtype: Tuple[Dict[int, Dict], int|None]
        """
        cur = self.sydent.db.cursor()
        res = cur.execute(
            "SELECT id, medium, address, room_id, sender, token FROM invite_tokens"
            " WHERE id > ? AND origin_id IS NULL LIMIT ?",
            (afterId, limit,)
        )
        rows = res.fetchall()

        # Dict of "id": {content}
        invite_tokens = {}

        maxId = None

        for row in rows:
            maxId, medium, address, room_id, sender, token = row
            invite_tokens[maxId] = {
                "origin_id": maxId,
                "medium": medium,
                "address": address,
                "room_id": room_id,
                "sender": sender,
                "token": token,
            }

        return (invite_tokens, maxId)

    def getLastTokenIdFromServer(self, server):
        """Returns the last known invite token that was received from the
        given server.

        :param server: The name of the origin server.
        :type server: str
        :returns a database id marking the last known invite token received
            from the given server. Returns 0 if no tokens have been received from
            this server.
        :rtype: int
        """
        cur = self.sydent.db.cursor()
        res = cur.execute("select max(origin_id), count(origin_id) from invite_tokens"
                          " where origin_server = ?", (server,))
        row = res.fetchone()

        if row[1] == 0:
            return 0

        return row[0]


    def markTokensAsSent(self, medium, address):
        """Mark invite tokens as sent.
        
        :param medium: The medium of the token.
        :type medium: str
        :param address: The address of the token.
        :type address: str
        """
        cur = self.sydent.db.cursor()

        cur.execute(
            "UPDATE invite_tokens SET sent_ts = ? WHERE medium = ? AND address = ?",
            (int(time.time()), medium, address,)
        )
        self.sydent.db.commit()

    def storeEphemeralPublicKey(self, publicKey, persistenceTs=None, originServer=None, originId=None, commit=True):
        """Stores an ephemeral public key in the database.
        
        :param publicKey: the ephemeral public key to store.
        :type publicKey: str
        :param persistenceTs: 
        :type persistenceTs: int
        :param originServer: the server this key was received from (if
            retrieved through replication).
        :type originServer: str
        :param originId: The id of the key in the DB of originServer. Used
            for determining if we've already received a key or not.
        :type originId: int
        :param commit: Whether DB changes should be committed by this
            function (or an external one).
        :type commit: bool
        """
        if originId and originServer:
            # Check if we've already seen this association from this server
            last_processed_id = self.getLastEphemeralPublicKeyIdFromServer(originServer)
            if int(originId) <= int(last_processed_id):
                logger.info("We have already seen key ID %s from %s. Ignoring.", originId, originServer)
                return

        if not persistenceTs:
            persistenceTs = int(time.time())
        cur = self.sydent.db.cursor()
        cur.execute(
            "INSERT INTO ephemeral_public_keys"
            " (public_key, persistence_ts, origin_server, origin_id)"
            " VALUES (?, ?, ?, ?)",
            (publicKey, persistenceTs, originServer, originId)
        )
        if commit:
            self.sydent.db.commit()

    def validateEphemeralPublicKey(self, publicKey):
        """Mark an ephemeral public key as validated.
        
        :param publicKey: An ephemeral public key.
        :type publicKey: str
        :returns true or false depending on whether validation was
            successful.
        :rtype: bool
        """
        cur = self.sydent.db.cursor()
        cur.execute(
            "UPDATE ephemeral_public_keys"
            " SET verify_count = verify_count + 1"
            " WHERE public_key = ?",
            (publicKey,)
        )
        self.sydent.db.commit()
        return cur.rowcount > 0

    def getEphemeralPublicKeysAfterId(self, afterId, limit):
        """Retrieves max `limit` ephemeral public keys after a given DB id.
        
        :param afterId: A database id to act as an offset. Keys after this id
            are returned.
        :type afterId: int
        :param limit: Max amount of database rows to return.
        :type limit: int
        :returns a tuple consisting of a list of ephemeral public keys (with
            key being the token's DB id) and the maximum table id that was
            extracted. Otherwise returns ({}, None) if no keys are found.
        :rtype: Tuple[Dict[int, Dict], int|None]
        """
        cur = self.sydent.db.cursor()
        res = cur.execute(
            "SELECT id, public_key, verify_count, persistence_ts FROM ephemeral_public_keys"
            " WHERE id > ? AND origin_id IS NULL LIMIT ?",
            (afterId, limit,)
        )
        rows = res.fetchall()

        # Dict of "id": {content}
        ephemeral_keys = {}

        maxId = None

        for row in rows:
            maxId, public_key, verify_count, persistence_ts = row
            ephemeral_keys[maxId] = {
                "public_key": public_key,
                "verify_count": verify_count,
                "persistence_ts": persistence_ts,
            }

        return (ephemeral_keys, maxId)

    def getLastEphemeralPublicKeyIdFromServer(self, server):
        """Returns the last known ephemeral public key that was received from
        the given server.

        :param server: The name of the origin server.
        :type server: str
        :returns the last known DB id received from the given server, or 0 if
            none have been received.
        :rtype: int
        """
        cur = self.sydent.db.cursor()
        res = cur.execute("select max(origin_id),count(origin_id) from ephemeral_public_keys"
                          " where origin_server = ?", (server,))
        row = res.fetchone()

        if not row or row[1] == 0:
            return 0

        return row[0]

    def getSenderForToken(self, token):
        """Returns the sender for a given invite token.
        
        :param token: The invite token.
        :type token: str
        :returns the sender of a given invite token or None if there isn't
            one.
        :rtype: str, None
        """
        cur = self.sydent.db.cursor()
        res = cur.execute(
            "SELECT sender FROM invite_tokens WHERE token = ?",
            (token,)
        )
        rows = res.fetchall()
        if rows:
            return rows[0][0]
        return None
