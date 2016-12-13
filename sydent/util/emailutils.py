# -*- coding: utf-8 -*-

# Copyright 2014-2015 OpenMarket Ltd
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

import logging
import socket
import random
import smtplib
import email.utils
import string
import twisted.python.log
import cgi
import urllib

import email.utils

from sydent.util import time_msec

logger = logging.getLogger(__name__)


def sendEmail(sydent, templateName, mailTo, substitutions):
        mailFrom = sydent.cfg.get('email', 'email.from')
        mailTemplateFile = sydent.cfg.get('email', templateName)

        myHostname = sydent.cfg.get('email', 'email.hostname')
        if myHostname == '':
            myHostname = socket.getfqdn()
        midRandom = "".join([random.choice(string.ascii_letters) for _ in range(16)])
        messageid = "<%d%s@%s>" % (time_msec(), midRandom, myHostname)

        allSubstitutions = {}
        allSubstitutions.update(substitutions)
        allSubstitutions.update({
            'messageid': messageid,
            'date': email.utils.formatdate(localtime=False),
            'to': mailTo,
            'from': mailFrom,
        })

        for k,v in allSubstitutions.items():
            allSubstitutions[k] = v.decode('utf8')
            allSubstitutions[k+"_forhtml"] = cgi.escape(v.decode('utf8'))
            allSubstitutions[k+"_forurl"] = urllib.quote(v)

        mailString = open(mailTemplateFile).read() % allSubstitutions
        rawFrom = email.utils.parseaddr(mailFrom)[1]
        rawTo = email.utils.parseaddr(mailTo)[1]
        if rawFrom == '' or rawTo == '':
            logger.info("Couldn't parse from / to address %s / %s", mailFrom, mailTo)
            raise EmailAddressException()
        mailServer = sydent.cfg.get('email', 'email.smtphost')
        mailPort = sydent.cfg.get('email', 'email.smtpport')
        mailUsername = sydent.cfg.get('email', 'email.smtpusername')
        mailPassword = sydent.cfg.get('email', 'email.smtppassword')
        mailTLSMode = sydent.cfg.get('email', 'email.tlsmode')
        logger.info("Sending mail to %s with mail server: %s" % (mailTo, mailServer,))
        try:
            if mailTLSMode == 'SSL' or mailTLSMode == 'TLS':
                smtp = smtplib.SMTP_SSL(mailServer, mailPort, myHostname)
            elif mailTLSMode == 'STARTTLS':
                smtp = smtplib.SMTP(mailServer, mailPort, myHostname)
                smtp.starttls()
            else:
                smtp = smtplib.SMTP(mailServer, mailPort, myHostname)
            if mailUsername != '':
                smtp.login(mailUsername, mailPassword)
            smtp.sendmail(rawFrom, rawTo, mailString.encode('utf-8'))
            smtp.quit()
        except Exception as origException:
            twisted.python.log.err()
            ese = EmailSendException()
            ese.cause = origException
            raise ese


class EmailAddressException(Exception):
    pass


class EmailSendException(Exception):
    pass
