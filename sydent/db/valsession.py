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

from twisted.internet import task

import sydent.util.tokenutils

from sydent.validators import ValidationSession, IncorrectClientSecretException, InvalidSessionIdException, \
    SessionExpiredException, SessionNotValidatedException
from sydent.util import time_msec

from random import SystemRandom


class ThreePidValSessionStore:
    def __init__(self, syd):
        self.sydent = syd
        self.random = SystemRandom()

        # Clean up old sessions every N minutes
        cb = task.LoopingCall(self.deleteOldSessions)
        cb.start(10 * 60.0)

    def getOrCreateTokenSession(self, medium, address, clientSecret):
        cur = self.sydent.db.cursor()

        cur.execute("select s.id, s.medium, s.address, s.clientSecret, s.validated, s.mtime, "
                    "t.token, t.sendAttemptNumber from threepid_validation_sessions s,threepid_token_auths t "
                    "where s.medium = ? and s.address = ? and s.clientSecret = ? and t.validationSession = s.id",
                    (medium, address, clientSecret))
        row = cur.fetchone()

        if row:
            s = ValidationSession(row[0], row[1], row[2], row[3], row[4], row[5])
            s.token = row[6]
            s.sendAttemptNumber = row[7]
            return s

        sid = self.addValSession(medium, address, clientSecret, time_msec(), commit=False)

        tokenString = sydent.util.tokenutils.generateTokenForMedium(medium)

        cur.execute("insert into threepid_token_auths (validationSession, token, sendAttemptNumber) values (?, ?, ?)",
                    (sid, tokenString, -1))
        self.sydent.db.commit()

        s = ValidationSession(sid, medium, address, clientSecret, False, time_msec())
        s.token = tokenString
        s.sendAttemptNumber = -1
        return s

    def addValSession(self, medium, address, clientSecret, mtime, commit=True):
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
        cur = self.sydent.db.cursor()

        cur.execute("update threepid_token_auths set sendAttemptNumber = ? where id = ?", (attemptNo, sid))
        self.sydent.db.commit()

    def setValidated(self, sid, validated, commit=True):
        """Set the validation status of a threepid validation session

        :param sid: The session ID
        :type sid: str

        :param validated: Whether a session is validated or not
        :type validated: bool

        :param commit: Whether to commit to the database. Used in applying other
            database operations atomically. Defaults to True
        :type bool: bool

        """
        cur = self.sydent.db.cursor()

        cur.execute("update threepid_validation_sessions set validated = ? where id = ?", (validated, sid))

        if commit:
            self.sydent.db.commit()

    def setMtime(self, sid, mtime):
        cur = self.sydent.db.cursor()

        cur.execute("update threepid_validation_sessions set mtime = ? where id = ?", (mtime, sid))
        self.sydent.db.commit()

    def getSessionById(self, sid):
         cur = self.sydent.db.cursor()

         cur.execute("select id, medium, address, clientSecret, validated, mtime from "+
             "threepid_validation_sessions where id = ?", (sid,))
         row = cur.fetchone()

         if not row:
             return None

         return ValidationSession(row[0], row[1], row[2], row[3], row[4], row[5])

    def getTokenSessionById(self, sid):
        cur = self.sydent.db.cursor()

        cur.execute("select s.id, s.medium, s.address, s.clientSecret, s.validated, s.mtime, "
                    "t.token, t.sendAttemptNumber from threepid_validation_sessions s,threepid_token_auths t "
                    "where s.id = ? and t.validationSession = s.id", (sid,))
        row = cur.fetchone()

        if row:
            s = ValidationSession(row[0], row[1], row[2], row[3], row[4], row[5])
            s.token = row[6]
            s.sendAttemptNumber = row[7]
            return s

        return None

    def next_link_differs(self, sid, token, next_link):
        """Check whether the specified session has already been validated with a
        next_link provided, and if so, check whether the current attempt is using the
        same next_link. If not, return True, otherwise return False

        :param sid: The session ID
        :type sid: str

        :param token: The validation token
        :type token: str

        :param next_link: The next_link parameter used in submitting this validation
        :type next_link: str

        :returns: Whether the provided next_link differs from the provided
            token's associated next_link. Returns False if the stored next_link
            value is NULL. Returns False regardless if session has not been validated.
        :rtype: bool
        """
        cur = self.sydent.db.cursor()

        # Check if this session has already been validated
        s = self.getTokenSessionById(sid)
        if not s.validated:
            # This session has not been validated before, we allow it to be
            return False

        sql = """
        SELECT next_link_used FROM threepid_token_auths
        WHERE validationSession = ? AND token = ?
        """
        cur.execute(sql, (sid, token))

        row = cur.fetchone()
        if not row:
            return False
        token_next_link = row[0]

        return token_next_link != next_link

    def set_next_link_for_token(self, sid, token, next_link):
        """Set which next_link was used when using a session token

        :param sid: The session ID
        :type sid: str

        :param token: The validation token
        :type token: str

        :param next_link: The next_link parameter used in submitting this validation
        :type next_link: str
        """
        cur = self.sydent.db.cursor()


        self.sydent.db.commit()

    def getValidatedSession(self, sid, clientSecret):
        """
        Retrieve a validated and still-valid session whose client secret matches the one passed in
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
