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

class JoinTokenStore(object):
    def __init__(self, sydent):
        self.sydent = sydent

    def storeToken(self, medium, address, roomId, sender, token, originServer=None, originId=None, commit=True):
        """Stores an invite token.
        
        :param medium: The medium of the token.
        :param address: The address of the token.
        :param roomId: The room ID this token is tied to.
        :param sender: The sender of the invite.
        :param token: The token itself.
        :param originServer: The server this invite originated from (if coming from replication).
        :param originId: The id of the token in the DB of originServer. Used
        for determining if we've already received a token or not.
        :param commit: Whether DB changes should be committed by this function (or an external one).
        :return:
        """
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
        :param address: The address of the 3PID.
        :return a list of invite tokens.
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

    def getTokensAfterId(self, afterId, limit):
        """Retrieves max `limit` invite tokens after a given DB id.
        
        :param afterId: A database id to act as an offset. Tokens after this id are returned.
        :param limit: Max amount of database rows to return.
        :returns a tuple consisting of a list of invite tokens and the maximum DB id that was extracted.
        """
        cur = self.sydent.db.cursor()
        res = cur.execute(
            "SELECT id, medium, address, room_id, sender, token FROM invite_tokens"
            " WHERE id > ? AND origin_id = NULL LIMIT ?",
            (afterId, limit,)
        )
        rows = res.fetchall()

        # Dict of "id": {content}
        invite_tokens = {}

        maxId = 0

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
        :returns a database id marking the last known invite token received
        from the given server.
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
        :param address: The address of the token.
        :return:
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
        :param persistenceTs: 
        :param originServer: the server this key was received from (if retrieved through replication).
        :param originId: The id of the key in the DB of originServer. Used
        for determining if we've already received a key or not.
        :param commit: Whether DB changes should be committed by this function (or an external one).
        :return:
        """
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
        :returns true or false depending on whether validation was successful.
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
        
        :param afterId: A database id to act as an offset. Keys after this id are returned.
        :param limit: Max amount of database rows to return.
        :returns a deferred
        """
        cur = self.sydent.db.cursor()
        res = cur.execute(
            "SELECT id, public_key, verify_count, persistence_ts FROM ephemeral_public_keys"
            " WHERE id > ? AND origin_id = NULL LIMIT ?",
            (afterId, limit,)
        )
        rows = res.fetchall()

        # Dict of "id": {content}
        epheremal_keys = {}

        maxId = 0

        for row in rows:
            maxId, public_key, verify_count, persistence_ts = row
            epheremal_keys[maxId] = {
                "public_key": public_key,
                "verify_count": verify_count,
                "persistence_ts": persistence_ts,
            }

        return (epheremal_keys, maxId)

    def getLastEphemeralPublicKeyIdFromServer(self, server):
        """Returns the last known ephemeral public key that was received from
        the given server.

        :param server: The name of the origin server.
        :returns the last known public key id received from the given server.
        """
        cur = self.sydent.db.cursor()
        res = cur.execute("select max(origin_id),count(origin_id) from ephemeral_public_keys"
                          " where origin_server = ?", (server,))
        row = res.fetchone()

        if row[1] == 0:
            return 0

        return row[0]

    def getSenderForToken(self, token):
        """Returns the sender for a given invite token.
        
        :param token: The invite token.
        :returns the sender of a given invite token or None if there isn't one.
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
