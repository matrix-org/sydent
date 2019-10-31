# -*- coding: utf-8 -*-

# Copyright 2015 OpenMarket Ltd
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

import time


class JoinTokenStore(object):
    def __init__(self, sydent):
        self.sydent = sydent

    def storeToken(self, medium, address, roomId, sender, token):
        cur = self.sydent.db.cursor()

        cur.execute("INSERT INTO invite_tokens"
                    " ('medium', 'address', 'room_id', 'sender', 'token', 'received_ts')"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (medium, address, roomId, sender, token, int(time.time())))
        self.sydent.db.commit()

    def getTokens(self, medium, address):
        cur = self.sydent.db.cursor()

        res = cur.execute(
            "SELECT medium, address, room_id, sender, token FROM invite_tokens"
            " WHERE medium = ? AND address = ? AND sent_ts IS NULL",
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

        return invite_tokens, maxId

    def markTokensAsSent(self, medium, address):
        cur = self.sydent.db.cursor()

        cur.execute(
            "UPDATE invite_tokens SET sent_ts = ? WHERE medium = ? AND address = ?",
            (int(time.time()), medium, address,)
        )
        self.sydent.db.commit()

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

        return ephemeral_keys, maxId

    def storeEphemeralPublicKey(self, publicKey):
        cur = self.sydent.db.cursor()
        cur.execute(
            "INSERT INTO ephemeral_public_keys"
            " (public_key, persistence_ts)"
            " VALUES (?, ?)",
            (publicKey, int(time.time()))
        )
        self.sydent.db.commit()

    def validateEphemeralPublicKey(self, publicKey):
        cur = self.sydent.db.cursor()
        cur.execute(
            "UPDATE ephemeral_public_keys"
            " SET verify_count = verify_count + 1"
            " WHERE public_key = ?",
            (publicKey,)
        )
        self.sydent.db.commit()
        return cur.rowcount > 0

    def getSenderForToken(self, token):
        cur = self.sydent.db.cursor()
        res = cur.execute(
            "SELECT sender FROM invite_tokens WHERE token = ?",
            (token,)
        )
        rows = res.fetchall()
        if rows:
            return rows[0][0]
        return None

    def deleteTokens(self, medium, address):
        cur = self.sydent.db.cursor()

        cur.execute(
            "DELETE FROM invite_tokens WHERE medium = ? AND address = ?",
            (medium, address,)
        )

        self.sydent.db.commit()
