# -*- coding: utf-8 -*-

# Copyright 2014 matrix.org
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

import smtplib
import os
import email.utils
import logging
import twisted.python.log

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from sydent.db.valsession import ThreePidValSessionStore
from sydent.validators import ValidationSession

from sydent.util import time_msec

from sydent.validators import IncorrectClientSecretException, SessionExpiredException

logger = logging.getLogger(__name__)


class EmailValidator:
    def __init__(self, sydent):
        self.sydent = sydent

    def requestToken(self, emailAddress, clientSecret, sendAttempt):
        valSessionStore = ThreePidValSessionStore(self.sydent)

        valSession = valSessionStore.getOrCreateTokenSession(medium='email', address=emailAddress,
                                                             clientSecret=clientSecret)

        valSessionStore.setMtime(valSession.id, time_msec())

        if valSession.sendAttemptNumber >= sendAttempt:
            logger.info("Send attempt %d given but session is on %d - not resending", (sendAttempt, valSession.sendAttemptNumber))
            return valSession.id

        myHostname = os.uname()[1]

        mailFrom = self.sydent.cfg.get('email', 'email.from').format(hostname=myHostname)
        mailTo = emailAddress

        mailTemplateFile = self.sydent.cfg.get('email', 'email.template')

        mailString = open(mailTemplateFile).read().format(token=valSession.token)

        msg = MIMEMultipart('alternative')
        msg['Subject'] = self.sydent.cfg.get('email', 'email.subject')
        msg['From'] = mailFrom
        msg['To'] = mailTo

        plainPart = MIMEText(mailString)
        msg.attach(plainPart)

        rawFrom = email.utils.parseaddr(mailFrom)[1]
        rawTo = email.utils.parseaddr(mailTo)[1]

        if rawFrom == '' or rawTo == '':
            logger.info("Couldn't parse from / to address %s / %s", mailFrom, mailTo)
            raise EmailAddressException()

        mailServer = self.sydent.cfg.get('email', 'email.smtphost')

        logger.info("Attempting to mail code %s to %s using mail server %s", valSession.token, rawTo, mailServer)

        try:
            smtp = smtplib.SMTP(mailServer)
            smtp.sendmail(rawFrom, rawTo, msg.as_string())
            smtp.quit()
        except Exception as origException:
            twisted.python.log.err()
            ese = EmailSendException()
            ese.cause = origException
            raise ese

        valSessionStore.setSendAttemptNumber(valSession.id, sendAttempt)

        return valSession.id

    def validateSessionWithToken(self, sid, clientSecret, token):
        valSessionStore = ThreePidValSessionStore(self.sydent)
        s = valSessionStore.getTokenSessionById(sid)
        if not s:
            logger.info("Session ID %s not found", (sid))
            return False

        if not clientSecret == s.clientSecret:
            logger.info("Incorrect client secret", (sid))
            raise IncorrectClientSecretException()

        if s.mtime + ValidationSession.THREEPID_SESSION_VALIDATION_TIMEOUT < time_msec():
            logger.info("Session expired")
            raise SessionExpiredException()

        # TODO once we can validate the token oob
        #if tokenObj.validated and clientSecret == tokenObj.clientSecret:
        #    return True

        if s.token == token:
            logger.info("Setting session %s as validated", (s.id))
            valSessionStore.setValidated(s.id, True)

            return {'success': True}
        else:
            logger.info("Incorrect token submitted")
            return False


class EmailAddressException(Exception):
    pass


class EmailSendException(Exception):
    pass
