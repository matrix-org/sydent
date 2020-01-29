# -*- coding: utf-8 -*-

# Copyright 2015 OpenMarket Ltd
# Copyright 2019 New Vector Ltd
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

    def updateToken(self, medium, address, room_id, sender, token, sent_ts, origin_server, origin_id, commit=True):
        """Process an invite token update received over replication.

        :param medium: The medium of the token.
        :type medium: str
        :param address: The address of the token.
        :type address: str
        :param room_id: The room ID this token is tied to.
        :type room_id: str
        :param sender: The sender of the invite.
        :type sender: str
        :param token: The token itself.
        :type token: str
        :param sent_ts: The timestamp at which the token has been delivered to the
            invitee (if applicable).
        :type sent_ts: str, None
        :param origin_server: The server the original version of the token originated
            from.
        :type origin_server: str
        :param origin_id: The id of the token in the DB of origin_server. Used
            for determining the row to update in the database.
        :type origin_id: int
        :param commit: Whether DB changes should be committed by this
            function (or an external one).
        :type commit: bool
        """
        cur = self.sydent.db.cursor()

        params = (medium, address, room_id, sender, token, sent_ts, origin_id)

        # Updates sent over replication include the origin_server and the origin_id as
        # seen from the server performing the update.
        # If we received an update to an invite that originated from this server,
        # use the id column to identify the invite to update, otherwise use the
        # origin_server and origin_id.
        # Note that we don't replicate 3PID invites that have been received over
        # replication, so we're sure that origin_server and origin_id are the right
        # ones (as opposed to, e.g., a server B replicating an invite on behalf of
        # another server A so that the origin_server and origin_id are for B rather
        # than A, from which that invite originated).
        if origin_server == self.sydent.server_name:
            where_clause = """
                WHERE id = ?
            """
        else:
            where_clause = """
                WHERE origin_id = ? AND origin_server = ?
            """
            params += (origin_server,)

        sql = """
            UPDATE invite_tokens
            SET medium = ?, address = ?, room_id = ?, sender = ?, token = ?, sent_ts = ?
        """

        sql += where_clause

        cur.execute(sql, params)

        if commit:
            self.sydent.db.commit()

    def getTokens(self, medium, address):
        """Retrieve the invite token(s) for a given 3PID medium and address.
        Filters out tokens which have expired.
        
        :param medium: The medium of the 3PID.
        :type medium: str
        :param address: The address of the 3PID.
        :type address: str
        :returns a list of invite tokens, or an empty list if no tokens found.
        :rtype: list[Dict[str, str]]
        """
        cur = self.sydent.db.cursor()

        res = cur.execute(
            "SELECT medium, address, room_id, sender, token, origin_server, received_ts FROM invite_tokens"
            " WHERE medium = ? AND address = ? AND sent_ts IS NULL",
            (medium, address,)
        )
        rows = res.fetchall()

        ret = []

        validity_period = self.sydent.invites_validity_period
        if validity_period is not None:
            min_valid_ts_ms = int(time.time() - validity_period/1000)

        for row in rows:
            medium, address, roomId, sender, token, origin_server, received_ts = row

            if (
                validity_period is not None
                and received_ts and received_ts < min_valid_ts_ms
            ):
                # Ignore this invite if it has expired.
                continue

            ret.append({
                "medium": medium,
                "address": address,
                "room_id": roomId,
                "sender": sender,
                "token": token,
                "origin_server": origin_server,
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

        # Insert a row for every updated invite in the updated_invites table so the
        # update is replicated to other servers.
        res = cur.execute(
            "SELECT id FROM invite_tokens WHERE medium = ? AND address = ?",
            (medium, address,)
        )

        rows = res.fetchall()

        cur.executemany(
            "INSERT INTO updated_invites (invite_id) VALUES (?)", rows
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

        return ephemeral_keys, maxId

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

    def getInviteUpdatesAfterId(self, last_id, limit):
        """Returns every updated token for which its update id is higher than the provided
        `last_id`, capped at `limit` tokens.

        :param last_id: The last ID processed during the previous run.
        :type last_id: int
        :param limit: The maximum number of results to return.
        :type limit: int
        :returns a tuple consisting of a list of invite tokens and the maximum DB id
            that was extracted from the table keeping track of the updates.
            Otherwise returns ([], None) if no tokens are found.
        :rtype: Tuple[List[Dict], int|None]

        """
        cur = self.sydent.db.cursor()

        # Retrieve the IDs of the invites that have been updated since the last time.
        res = cur.execute(
            """
                SELECT u.id, t.id, medium, address, room_id, sender, token, sent_ts,
                    origin_server, origin_id
                FROM updated_invites AS u
                    LEFT JOIN invite_tokens AS t ON (t.id = u.invite_id)
                WHERE u.id > ? ORDER BY u.id ASC LIMIT ?;
            """,
            (last_id, limit),
        )

        rows = res.fetchall()

        max_id = None

        # Retrieve each invite and append it to a list.
        invites = []
        for row in rows:
            max_id, invite_id, medium, address, room_id, sender, token, sent_ts, origin_server, origin_id = row
            # Append a new dict to the list containing the token's metadata,
            # including an `origin_id` and an `origin_server` so that the receiving end
            # can figure out which invite to update in its local database. If the token
            # originated from this server, use its local ID as the value for
            # `origin_id`, and the local server's server_name for `origin_server`.
            invites.append(
                {
                    "origin_id": origin_id if origin_id is not None else invite_id,
                    "origin_server": origin_server if origin_server is not None else self.sydent.server_name,
                    "medium": medium,
                    "address": address,
                    "room_id": room_id,
                    "sender": sender,
                    "token": token,
                    "sent_ts": sent_ts,
                }
            )

        self.sydent.db.commit()

        return invites, max_id
