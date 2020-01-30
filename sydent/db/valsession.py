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
from __future__ import absolute_import

import sydent.util.tokenutils

from sydent.validators import ValidationSession, IncorrectClientSecretException, InvalidSessionIdException, \
    SessionExpiredException, SessionNotValidatedException
from sydent.util import time_msec

from random import SystemRandom


class ThreePidValSessionStore:
    def __init__(self, syd):
        self.sydent = syd
        self.random = SystemRandom()

    def getOrCreateTokenSession(self, medium, address, clientSecret):
        """
        Retrieves the validation session for a given medium, address and client secret,
        or creates one if none was found.

        :param medium: The medium to use when looking up or creating the session.
        :type medium: unicode
        :param address: The address to use when looking up or creating the session.
        :type address: unicode
        :param clientSecret: The client secret to use when looking up or creating the
            session.
        :type clientSecret: unicode

        :return: The session that was retrieved or created.
        :rtype: ValidationSession
        """
        cur = self.sydent.db.cursor()

        cur.execute("select s.id, s.medium, s.address, s.clientSecret, s.validated, s.mtime, "
                    "t.token, t.sendAttemptNumber from threepid_validation_sessions s,threepid_token_auths t "
                    "where s.medium = ? and s.address = ? and s.clientSecret = ? and t.validationSession = s.id",
                    (medium, address, clientSecret))
        row = cur.fetchone()

        if row:
            s = ValidationSession(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7])
            return s

        sid = self.addValSession(medium, address, clientSecret, time_msec(), commit=False)

        tokenString = sydent.util.tokenutils.generateTokenForMedium(medium)

        cur.execute("insert into threepid_token_auths (validationSession, token, sendAttemptNumber) values (?, ?, ?)",
                    (sid, tokenString, -1))
        self.sydent.db.commit()

        s = ValidationSession(sid, medium, address, clientSecret, False, time_msec(), tokenString, -1)
        return s

    def addValSession(self, medium, address, clientSecret, mtime, commit=True):
        """
        Creates a validation session with the given parameters.

        :param medium: The medium to create the session for.
        :type medium: unicode
        :param address: The address to create the session for.
        :type address: unicode
        :param clientSecret: The client secret to use when looking up or creating the
            session.
        :type clientSecret: unicode
        :param mtime: The current time in milliseconds.
        :type mtime: int
        :param commit: Whether to commit the transaction after executing the insert
            statement.
        :type commit: bool

        :return: The ID of the created session.
        :rtype: int
        """
        cur = self.sydent.db.cursor()

        # Let's make up a random sid rather than using sequential ones. This
        # should be safe enough given we reap old sessions.
        sid = self.random.randint(0, 2 ** 31)

        cur.execute("insert into threepid_validation_sessions ('id', 'medium', 'address', 'clientSecret', 'mtime')" +
            " values (?, ?, ?, ?, ?)", (sid, medium, address, clientSecret, mtime))
        if commit:
            self.sydent.db.commit()
        return sid

    def setSendAttemptNumber(self, sid, attemptNo):
        """
        Updates the send attempt number for the session with the given ID.

        :param sid: The ID of the session to update
        :type sid: unicode
        :param attemptNo: The send attempt number to update the session with.
        :type attemptNo: int
        """
        cur = self.sydent.db.cursor()

        cur.execute("update threepid_token_auths set sendAttemptNumber = ? where id = ?", (attemptNo, sid))
        self.sydent.db.commit()

    def setValidated(self, sid, validated):
        """
        Updates a session to set the validated flag to the given value.

        :param sid: The ID of the session to update.
        :type sid: unicode
        :param validated: The value to set the validated flag.
        :type validated: bool
        """
        cur = self.sydent.db.cursor()

        cur.execute("update threepid_validation_sessions set validated = ? where id = ?", (validated, sid))
        self.sydent.db.commit()

    def setMtime(self, sid, mtime):
        """
        Set the time of the last send attempt for the session with the given ID

        :param sid: The ID of the session to update.
        :type sid: unicode
        :param mtime: The time of the last send attempt for that session.
        :type mtime: int
        """
        cur = self.sydent.db.cursor()

        cur.execute("update threepid_validation_sessions set mtime = ? where id = ?", (mtime, sid))
        self.sydent.db.commit()

    def getSessionById(self, sid):
        """
        Retrieves the session matching the given sid.

        :param sid: The ID of the session to retrieve.
        :type sid: unicode

        :return: The retrieved session, or None if no session could be found with that
            sid.
        :rtype: ValidationSession or None
        """
        cur = self.sydent.db.cursor()

        cur.execute("select id, medium, address, clientSecret, validated, mtime from "+
            "threepid_validation_sessions where id = ?", (sid,))
        row = cur.fetchone()

        if not row:
            return None

        return ValidationSession(row[0], row[1], row[2], row[3], row[4], row[5], None, None)

    def getTokenSessionById(self, sid):
        """
        Retrieves a validation session using the session's ID.

        :param sid: The ID of the session to retrieve.
        :type sid: unicode

        :return: The validation session, or None if no session was found with that ID.
        :rtype: ValidationSession or None
        """
        cur = self.sydent.db.cursor()

        cur.execute("select s.id, s.medium, s.address, s.clientSecret, s.validated, s.mtime, "
                    "t.token, t.sendAttemptNumber from threepid_validation_sessions s,threepid_token_auths t "
                    "where s.id = ? and t.validationSession = s.id", (sid,))
        row = cur.fetchone()

        if row:
            s = ValidationSession(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7])
            return s

        return None

    def getValidatedSession(self, sid, clientSecret):
        """
        Retrieve a validated and still-valid session whose client secret matches the
        one passed in.

        :param sid: The ID of the session to retrieve.
        :type sid: unicode
        :param clientSecret: A client secret to check against the one retrieved from
            the database.
        :type clientSecret: unicode

        :return: The retrieved session.
        :rtype: ValidationSession

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

        if not s.clientSecret == clientSecret:
            raise IncorrectClientSecretException()

        if s.mtime + ValidationSession.THREEPID_SESSION_VALID_LIFETIME_MS < time_msec():
            raise SessionExpiredException()

        if not s.validated:
            raise SessionNotValidatedException()

        return s

    def deleteOldSessions(self):
        """Delete old threepid validation sessions that are long expired.
        """

        cur = self.sydent.db.cursor()

        delete_before_ts = time_msec() - 5 * ValidationSession.THREEPID_SESSION_VALID_LIFETIME_MS

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
