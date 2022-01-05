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
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from sydent.sydent import Sydent


class JoinTokenStore:
    def __init__(self, sydent: "Sydent") -> None:
        self.sydent = sydent

    def storeToken(
        self, medium: str, normalised_address: str, roomId: str, sender: str, token: str
    ) -> None:
        """
        Store a new invite token and its metadata. Please note that email
        addresses need to be casefolded before calling this function.

        :param medium: The medium of the 3PID the token is associated to.
        :param normalised_address: The address of the 3PID the token is associated to.
        :param roomId: The ID of the room the 3PID is invited in.
        :param sender: The MXID of the user that sent the invite.
        :param token: The token to store.
        """

        cur = self.sydent.db.cursor()

        cur.execute(
            "INSERT INTO invite_tokens"
            " ('medium', 'address', 'room_id', 'sender', 'token', 'received_ts')"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (medium, normalised_address, roomId, sender, token, int(time.time())),
        )
        self.sydent.db.commit()

    def getTokens(self, medium: str, address: str) -> List[Dict[str, str]]:
        """
        Retrieves the pending invites tokens for this 3PID that haven't been delivered
        yet.

        :param medium: The medium of the 3PID to get tokens for.
        :param address: The address of the 3PID to get tokens for.

        :return: A list of dicts, each containing a pending token and its metadata for
            this 3PID.
        """
        cur = self.sydent.db.cursor()

        res = cur.execute(
            "SELECT medium, address, room_id, sender, token FROM invite_tokens"
            " WHERE medium = ? AND address = ? AND sent_ts IS NULL",
            (
                medium,
                address,
            ),
        )
        rows: List[Tuple[str, str, str, str, str]] = res.fetchall()

        ret = []

        for row in rows:
            medium, address, roomId, sender, token = row
            ret.append(
                {
                    "medium": medium,
                    "address": address,
                    "room_id": roomId,
                    "sender": sender,
                    "token": token,
                }
            )

        return ret

    def markTokensAsSent(self, medium: str, address: str) -> None:
        """
        Updates the invite tokens associated with a given 3PID to mark them as
        delivered to a homeserver so they're not delivered again in the future.

        :param medium: The medium of the 3PID to update tokens for.
        :param address: The address of the 3PID to update tokens for.
        """
        cur = self.sydent.db.cursor()

        cur.execute(
            "UPDATE invite_tokens SET sent_ts = ? WHERE medium = ? AND address = ?",
            (
                int(time.time()),
                medium,
                address,
            ),
        )
        self.sydent.db.commit()

    def storeEphemeralPublicKey(self, publicKey: str) -> None:
        """
        Saves the provided ephemeral public key.

        :param publicKey: The key to store.
        """
        cur = self.sydent.db.cursor()
        cur.execute(
            "INSERT INTO ephemeral_public_keys"
            " (public_key, persistence_ts)"
            " VALUES (?, ?)",
            (publicKey, int(time.time())),
        )
        self.sydent.db.commit()

    def validateEphemeralPublicKey(self, publicKey: str) -> bool:
        """
        Checks if an ephemeral public key is valid, and, if it is, updates its
        verification count.

        :param publicKey: The public key to validate.

        :return: Whether the key is valid.
        """
        cur = self.sydent.db.cursor()
        cur.execute(
            "UPDATE ephemeral_public_keys"
            " SET verify_count = verify_count + 1"
            " WHERE public_key = ?",
            (publicKey,),
        )
        self.sydent.db.commit()
        return cur.rowcount > 0

    def getSenderForToken(self, token: str) -> Optional[str]:
        """
        Retrieves the MXID of the user that sent the invite the provided token is for.

        :param token: The token to retrieve the sender of.

        :return: The invite's sender, or None if the token doesn't match an existing
            invite.
        """
        cur = self.sydent.db.cursor()
        res = cur.execute("SELECT sender FROM invite_tokens WHERE token = ?", (token,))
        rows: List[Tuple[str]] = res.fetchall()
        if rows:
            return rows[0][0]
        return None

    def deleteTokens(self, medium: str, address: str) -> None:
        """
        Deletes every token for a given 3PID.

        :param medium: The medium of the 3PID to delete tokens for.
        :param address: The address of the 3PID to delete tokens for.
        """
        cur = self.sydent.db.cursor()

        cur.execute(
            "DELETE FROM invite_tokens WHERE medium = ? AND address = ?",
            (
                medium,
                address,
            ),
        )

        self.sydent.db.commit()
