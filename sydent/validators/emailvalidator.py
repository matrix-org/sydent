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

import smtplib
import os
import email.utils
import logging
import random
import string
import urllib
import twisted.python.log

import email.utils

from sydent.db.valsession import ThreePidValSessionStore
from sydent.validators import ValidationSession

from sydent.util import time_msec

from sydent.validators import IncorrectClientSecretException, SessionExpiredException

logger = logging.getLogger(__name__)


class EmailValidator:
    def __init__(self, sydent):
        self.sydent = sydent

    def requestToken(self, emailAddress, clientSecret, sendAttempt, nextLink, ipaddress=None):
        valSessionStore = ThreePidValSessionStore(self.sydent)

        valSession = valSessionStore.getOrCreateTokenSession(medium='email', address=emailAddress,
                                                             clientSecret=clientSecret)

        valSessionStore.setMtime(valSession.id, time_msec())

        if int(valSession.sendAttemptNumber) >= int(sendAttempt):
            logger.info("Not mailing code because current send attempt (%d) is not less than given send attempt (%s)", int(sendAttempt), int(valSession.sendAttemptNumber))
            return valSession.id

        myHostname = os.uname()[1]
        midRandom = "".join([random.choice(string.ascii_letters) for _ in range(16)])
        messageid = "%d%s@%s" % (time_msec(), midRandom, myHostname)
        ipstring = ipaddress if ipaddress else u"an unknown location"

        mailTo = emailAddress
        mailFrom = self.sydent.cfg.get('email', 'email.from')

        mailTemplateFile = self.sydent.cfg.get('email', 'email.template')

        mailString = open(mailTemplateFile).read() % {
            'date': email.utils.formatdate(localtime=False),
            'to': mailTo,
            'from': mailFrom,
            'messageid': messageid,
            'ipaddress': ipstring,
            'link': self.makeValidateLink(valSession, clientSecret, nextLink),
            'token': valSession.token,
        }

        rawFrom = email.utils.parseaddr(mailFrom)[1]
        rawTo = email.utils.parseaddr(mailTo)[1]

        if rawFrom == '' or rawTo == '':
            logger.info("Couldn't parse from / to address %s / %s", mailFrom, mailTo)
            raise EmailAddressException()

        mailServer = self.sydent.cfg.get('email', 'email.smtphost')

        logger.info("Attempting to mail code %s to %s using mail server %s", valSession.token, rawTo, mailServer)

        try:
            smtp = smtplib.SMTP(mailServer)
            smtp.sendmail(rawFrom, rawTo, mailString)
            smtp.quit()
        except Exception as origException:
            twisted.python.log.err()
            ese = EmailSendException()
            ese.cause = origException
            raise ese

        valSessionStore.setSendAttemptNumber(valSession.id, sendAttempt)

        return valSession.id

    def makeValidateLink(self, valSession, clientSecret, nextLink):
        base = self.sydent.cfg.get('http', 'client_http_base')
        link = "%s/_matrix/identity/api/v1/validate/email/submitToken?token=%s&clientSecret=%s&sid=%d" % (
            base,
            urllib.quote(valSession.token),
            urllib.quote(clientSecret),
            valSession.id,
        )
        if nextLink:
            link += "&nextLink=%s" % (urllib.quote(nextLink))
        return link

    def validateSessionWithToken(self, sid, clientSecret, token):
        valSessionStore = ThreePidValSessionStore(self.sydent)
        s = valSessionStore.getTokenSessionById(sid)
        if not s:
            return False

        if not clientSecret == s.clientSecret:
            raise IncorrectClientSecretException()

        if s.mtime + ValidationSession.THREEPID_SESSION_VALIDATION_TIMEOUT < time_msec():
            raise SessionExpiredException()

        # TODO once we can validate the token oob
        #if tokenObj.validated and clientSecret == tokenObj.clientSecret:
        #    return True

        if s.token == token:
            valSessionStore.setValidated(s.id, True)

            return {'success': True}
        else:
            return False


class EmailAddressException(Exception):
    pass


class EmailSendException(Exception):
    pass
