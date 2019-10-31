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

    def setValidated(self, sid, validated):
        cur = self.sydent.db.cursor()

        cur.execute("update threepid_validation_sessions set validated = ? where id = ?", (validated, sid))
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
