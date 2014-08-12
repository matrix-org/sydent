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

import sydent.util.tokenutils
import smtplib
import os
import email.utils
import logging
import twisted.python.log
import time

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from sydent.db.threepidtoken import ThreePidTokenStore

from sydent.util import validationutils


logger = logging.getLogger(__name__)

class EmailValidator:
    THREEPID_ASSOCIATION_LIFETIME_MS = 100 * 365 * 24 * 60 * 60 * 1000

    def __init__(self, sydent):
        self.sydent = sydent

    def requestToken(self, emailAddress, clientSecret):
        tokenString = sydent.util.tokenutils.generateNumericTokenOfLength(
            int(self.sydent.cfg.get('email', 'token.length')))

        myHostname = os.uname()[1]

        mailFrom = self.sydent.cfg.get('email', 'email.from').format(hostname=myHostname)
        mailTo = emailAddress

        mailTemplateFile = self.sydent.cfg.get('email', 'email.template')

        mailString = open(mailTemplateFile).read().format(token=tokenString)

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

        logger.info("Attempting to mail code %s to %s using mail server %s", tokenString, rawTo, mailServer)

        try:
            smtp = smtplib.SMTP(mailServer)
            smtp.sendmail(rawFrom, rawTo, msg.as_string())
            smtp.quit()
        except Exception as origException:
            twisted.python.log.err()
            ese = EmailSendException()
            ese.cause = origException
            raise ese

        threePidStore = ThreePidTokenStore(self.sydent)
        createdMs = int(time.time() * 1000.0)
        tokenId = threePidStore.addToken('email', rawTo, tokenString, clientSecret, createdMs)

        return tokenId

    def validateToken(self, tokenId, clientSecret, token, mxId):
        """
        XXX: This also binds the validated 3pid to an mxId so the structure needs a rethink.
        """
        threePidStore = ThreePidTokenStore(self.sydent)
        tokenObj = threePidStore.getTokenById(tokenId)
        if not tokenObj:
            return False

        # TODO once we can validate the token oob
        #if tokenObj.validated and clientSecret == tokenObj.clientSecret:
        #    return True

        if tokenObj.tokenString == token:
            createdAt = int(time.time() * 1000.0)
            expires = createdAt + EmailValidator.THREEPID_ASSOCIATION_LIFETIME_MS

            cur = self.sydent.db.cursor()

            # sqlite's support for upserts is atrocious but this is temporary anyway
            cur.execute("insert or replace into threepid_associations ('medium', 'address', 'mxId', 'createdAt', 'expires')"+
                " values (?, ?, ?, ?, ?)",
                (tokenObj.medium, tokenObj.address, mxId, createdAt, expires))
            self.sydent.db.commit()

            return validationutils.signedThreePidAssociation(self.sydent, tokenObj.medium, tokenObj.address,
                                                             createdAt, expires, mxId)
        else:
            return False

class EmailAddressException(Exception):
    pass

class EmailSendException(Exception):
    pass
