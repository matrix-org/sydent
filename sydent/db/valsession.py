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

from random import SystemRandom
from typing import TYPE_CHECKING, Optional, Tuple

import sydent.util.tokenutils
from sydent.util import time_msec
from sydent.validators import (
    THREEPID_SESSION_VALID_LIFETIME_MS,
    IncorrectClientSecretException,
    InvalidSessionIdException,
    SessionExpiredException,
    SessionNotValidatedException,
    TokenInfo,
    ValidationSession,
)

if TYPE_CHECKING:
    from sydent.sydent import Sydent


class ThreePidValSessionStore:
    def __init__(self, syd: "Sydent") -> None:
        self.sydent = syd
        self.random = SystemRandom()

    def getOrCreateTokenSession(
        self, medium: str, address: str, clientSecret: str
    ) -> Tuple[ValidationSession, TokenInfo]:
        """
        Retrieves the validation session for a given medium, address and client secret,
        or creates one if none was found.

        :param medium: The medium to use when looking up or creating the session.
        :param address: The address to use when looking up or creating the session.
        :param clientSecret: The client secret to use when looking up or creating the
            session.

        :return: The session that was retrieved or created.
        """
        cur = self.sydent.db.cursor()

        cur.execute(
            "select s.id, s.medium, s.address, s.clientSecret, s.validated, s.mtime, "
            "t.token, t.sendAttemptNumber from threepid_validation_sessions s,threepid_token_auths t "
            "where s.medium = ? and s.address = ? and s.clientSecret = ? and t.validationSession = s.id",
            (medium, address, clientSecret),
        )
        row: Optional[
            Tuple[int, str, str, str, Optional[int], int, str, int]
        ] = cur.fetchone()

        if row:
            session = ValidationSession(
                row[0], row[1], row[2], row[3], bool(row[4]), row[5]
            )
            token_info = TokenInfo(row[6], row[7])
            return session, token_info

        sid = self.addValSession(
            medium, address, clientSecret, time_msec(), commit=False
        )

        tokenString = sydent.util.tokenutils.generateTokenForMedium(medium)

        cur.execute(
            "insert into threepid_token_auths (validationSession, token, sendAttemptNumber) values (?, ?, ?)",
            (sid, tokenString, -1),
        )
        self.sydent.db.commit()

        session = ValidationSession(
            sid,
            medium,
            address,
            clientSecret,
            False,
            time_msec(),
        )
        token_info = TokenInfo(tokenString, -1)
        return session, token_info

    def addValSession(
        self,
        medium: str,
        address: str,
        clientSecret: str,
        mtime: int,
        commit: bool = True,
    ) -> int:
        """
        Creates a validation session with the given parameters.

        :param medium: The medium to create the session for.
        :param address: The address to create the session for.
        :param clientSecret: The client secret to use when looking up or creating the
            session.
        :param mtime: The current time in milliseconds.
        :param commit: Whether to commit the transaction after executing the insert
            statement.

        :return: The ID of the created session.
        """
        cur = self.sydent.db.cursor()

        # Let's make up a random sid rather than using sequential ones. This
        # should be safe enough given we reap old sessions.
        sid = self.random.randint(0, 2 ** 31)

        cur.execute(
            "insert into threepid_validation_sessions ('id', 'medium', 'address', 'clientSecret', 'mtime')"
            + " values (?, ?, ?, ?, ?)",
            (sid, medium, address, clientSecret, mtime),
        )
        if commit:
            self.sydent.db.commit()
        return sid

    def setSendAttemptNumber(self, sid: int, attemptNo: int) -> None:
        """
        Updates the send attempt number for the session with the given ID.

        :param sid: The ID of the session to update
        :param attemptNo: The send attempt number to update the session with.
        """
        cur = self.sydent.db.cursor()

        cur.execute(
            "update threepid_token_auths set sendAttemptNumber = ? where id = ?",
            (attemptNo, sid),
        )
        self.sydent.db.commit()

    def setValidated(self, sid: int, validated: bool) -> None:
        """
        Updates a session to set the validated flag to the given value.

        :param sid: The ID of the session to update.
        :param validated: The value to set the validated flag.
        """
        cur = self.sydent.db.cursor()

        cur.execute(
            "update threepid_validation_sessions set validated = ? where id = ?",
            (validated, sid),
        )
        self.sydent.db.commit()

    def setMtime(self, sid: int, mtime: int) -> None:
        """
        Set the time of the last send attempt for the session with the given ID

        :param sid: The ID of the session to update.
        :param mtime: The time of the last send attempt for that session.
        """
        cur = self.sydent.db.cursor()

        cur.execute(
            "update threepid_validation_sessions set mtime = ? where id = ?",
            (mtime, sid),
        )
        self.sydent.db.commit()

    def getSessionById(self, sid: int) -> Optional[ValidationSession]:
        """
        Retrieves the session matching the given sid.

        :param sid: The ID of the session to retrieve.

        :return: The retrieved session, or None if no session could be found with that
            sid.
        """
        cur = self.sydent.db.cursor()

        cur.execute(
            "select id, medium, address, clientSecret, validated, mtime from "
            + "threepid_validation_sessions where id = ?",
            (sid,),
        )
        row: Optional[Tuple[int, str, str, str, Optional[int], int]] = cur.fetchone()

        if not row:
            return None

        return ValidationSession(row[0], row[1], row[2], row[3], bool(row[4]), row[5])

    def getTokenSessionById(
        self, sid: int
    ) -> Optional[Tuple[ValidationSession, TokenInfo]]:
        """
        Retrieves a validation session using the session's ID.

        :param sid: The ID of the session to retrieve.

        :return: The validation session, or None if no session was found with that ID.
        """
        cur = self.sydent.db.cursor()

        cur.execute(
            "select s.id, s.medium, s.address, s.clientSecret, s.validated, s.mtime, "
            "t.token, t.sendAttemptNumber from threepid_validation_sessions s,threepid_token_auths t "
            "where s.id = ? and t.validationSession = s.id",
            (sid,),
        )
        row: Optional[Tuple[int, str, str, str, Optional[int], int, str, int]]
        row = cur.fetchone()

        if row:
            s = ValidationSession(row[0], row[1], row[2], row[3], bool(row[4]), row[5])
            t = TokenInfo(row[6], row[7])
            return s, t

        return None

    def getValidatedSession(self, sid: int, client_secret: str) -> ValidationSession:
        """
        Retrieve a validated and still-valid session whose client secret matches the
        one passed in.

        :param sid: The ID of the session to retrieve.
        :param client_secret: A client secret to check against the one retrieved from
            the database.

        :return: The retrieved session.

        :raise InvalidSessionIdException: No session could be found with this ID.
        :raise IncorrectClientSecretException: The session's client secret doesn't
            match the one passed in.
        :raise SessionExpiredException: The session exists but has expired.
        :raise SessionNotValidatedException: The session exists but hasn't been
            validated yet.
        """
        s = self.getSessionById(sid)

        if not s:
            raise InvalidSessionIdException()

        if not s.client_secret == client_secret:
            raise IncorrectClientSecretException()

        if s.mtime + THREEPID_SESSION_VALID_LIFETIME_MS < time_msec():
            raise SessionExpiredException()

        if not s.validated:
            raise SessionNotValidatedException()

        return s

    def deleteOldSessions(self) -> None:
        """Delete old threepid validation sessions that are long expired."""

        cur = self.sydent.db.cursor()

        delete_before_ts = time_msec() - 5 * THREEPID_SESSION_VALID_LIFETIME_MS

        sql = """
            DELETE FROM threepid_validation_sessions
            WHERE mtime < ?
        """
        cur.execute(sql, (delete_before_ts,))

        sql = """
            DELETE FROM threepid_token_auths
            WHERE validationSession NOT IN (
                SELECT id FROM threepid_validation_sessions
            )
        """
        cur.execute(sql)

        self.sydent.db.commit()
