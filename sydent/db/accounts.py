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

from typing import TYPE_CHECKING, Optional, Tuple

from sydent.users.accounts import Account

if TYPE_CHECKING:
    from sydent.sydent import Sydent


class AccountStore:
    def __init__(self, sydent: "Sydent") -> None:
        self.sydent = sydent

    def getAccountByToken(self, token: str) -> Optional[Account]:
        """
        Select the account matching the given token, if any.

        :param token: The token to identify the account, if any.

        :return: The account matching the token, or None if no account matched.
        """
        cur = self.sydent.db.cursor()
        res = cur.execute(
            "select a.user_id, a.created_ts, a.consent_version from accounts a, tokens t "
            "where t.user_id = a.user_id and t.token = ?",
            (token,),
        )

        row: Optional[Tuple[str, int, Optional[str]]] = res.fetchone()
        if row is None:
            return None

        return Account(*row)

    def storeAccount(
        self, user_id: str, creation_ts: int, consent_version: Optional[str]
    ) -> None:
        """
        Stores an account for the given user ID.

        :param user_id: The Matrix user ID to create an account for.
        :param creation_ts: The timestamp in milliseconds.
        :param consent_version: The version of the terms of services that the user last
            accepted.
        """
        cur = self.sydent.db.cursor()
        cur.execute(
            "insert or ignore into accounts (user_id, created_ts, consent_version) "
            "values (?, ?, ?)",
            (user_id, creation_ts, consent_version),
        )
        self.sydent.db.commit()

    def setConsentVersion(self, user_id: str, consent_version: Optional[str]) -> None:
        """
        Saves that the given user has agreed to all of the terms in the document of the
        given version.

        :param user_id: The Matrix ID of the user that has agreed to the terms.
        :param consent_version: The version of the document the user has agreed to.
        """
        cur = self.sydent.db.cursor()
        cur.execute(
            "update accounts set consent_version = ? where user_id = ?",
            (consent_version, user_id),
        )
        self.sydent.db.commit()

    def addToken(self, user_id: str, token: str) -> None:
        """
        Stores the authentication token for a given user.

        :param user_id: The Matrix user ID to save the given token for.
        :param token: The token to store for that user ID.
        """
        cur = self.sydent.db.cursor()
        cur.execute(
            "insert into tokens (user_id, token) values (?, ?)",
            (user_id, token),
        )
        self.sydent.db.commit()

    def delToken(self, token: str) -> int:
        """
        Deletes an authentication token from the database.

        :param token: The token to delete from the database.
        """
        cur = self.sydent.db.cursor()
        cur.execute(
            "delete from tokens where token = ?",
            (token,),
        )
        deleted = cur.rowcount
        self.sydent.db.commit()
        return deleted
