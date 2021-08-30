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

import email.utils
import logging
import random
import smtplib
import socket
import string
import urllib
from html import escape
from typing import TYPE_CHECKING, Dict

import twisted.python.log

from sydent.util import time_msec
from sydent.util.tokenutils import generateAlphanumericTokenOfLength

if TYPE_CHECKING:
    from sydent.sydent import Sydent

logger = logging.getLogger(__name__)


def sendEmail(
    sydent: "Sydent", templateFile: str, mailTo: str, substitutions: Dict[str, str]
) -> None:
    """
    Sends an email with the given parameters.

    :param sydent: The Sydent instance to use when building the configuration to send the
        email with.
    :param templateFile: The filename of the template to use when building the body of the
        email.
    :param mailTo: The email address to send the email to.
    :param substitutions: The substitutions to use with the template.
    """
    mailFrom = sydent.cfg.get("email", "email.from")

    myHostname = sydent.cfg.get("email", "email.hostname")
    if myHostname == "":
        myHostname = socket.getfqdn()
    midRandom = "".join([random.choice(string.ascii_letters) for _ in range(16)])
    messageid = "<%d%s@%s>" % (time_msec(), midRandom, myHostname)

    substitutions.update(
        {
            "messageid": messageid,
            "date": email.utils.formatdate(localtime=False),
            "to": mailTo,
            "from": mailFrom,
        }
    )

    # use jinja for rendering if jinja templates are present
    if templateFile.endswith(".j2"):
        # We add randomize the multipart boundary to stop user input from
        # conflicting with it.
        substitutions["multipart_boundary"] = generateAlphanumericTokenOfLength(32)
        template = sydent.template_environment.get_template(templateFile)
        mailString = template.render(substitutions)
    else:
        allSubstitutions = {}
        for k, v in substitutions.items():
            allSubstitutions[k] = v
            allSubstitutions[k + "_forhtml"] = escape(v)
            allSubstitutions[k + "_forurl"] = urllib.parse.quote(v)
        allSubstitutions["multipart_boundary"] = generateAlphanumericTokenOfLength(32)
        with open(templateFile) as template_file:
            mailString = template_file.read() % allSubstitutions

    parsedFrom = email.utils.parseaddr(mailFrom)[1]
    parsedTo = email.utils.parseaddr(mailTo)[1]
    if parsedFrom == "" or parsedTo == "":
        logger.info("Couldn't parse from / to address %s / %s", mailFrom, mailTo)
        raise EmailAddressException()

    if parsedTo != mailTo:
        logger.info("Parsed to address changed the address: %s -> %s", mailTo, parsedTo)
        raise EmailAddressException()

    mailServer = sydent.cfg.get("email", "email.smtphost")
    mailPort = sydent.cfg.get("email", "email.smtpport")
    mailUsername = sydent.cfg.get("email", "email.smtpusername")
    mailPassword = sydent.cfg.get("email", "email.smtppassword")
    mailTLSMode = sydent.cfg.get("email", "email.tlsmode")
    logger.info(
        "Sending mail to %s with mail server: %s"
        % (
            mailTo,
            mailServer,
        )
    )
    try:
        smtp: smtplib.SMTP
        if mailTLSMode == "SSL" or mailTLSMode == "TLS":
            smtp = smtplib.SMTP_SSL(mailServer, mailPort, myHostname)
        elif mailTLSMode == "STARTTLS":
            smtp = smtplib.SMTP(mailServer, mailPort, myHostname)
            smtp.starttls()
        else:
            smtp = smtplib.SMTP(mailServer, mailPort, myHostname)
        if mailUsername != "":
            smtp.login(mailUsername, mailPassword)

        # We're using the parsing above to do basic validation, but instead of
        # failing it may munge the address it returns. So we should *not* use
        # that parsed address, as it may not match any validation done
        # elsewhere.
        smtp.sendmail(mailFrom, mailTo, mailString.encode("utf-8"))
        smtp.quit()
    except Exception as origException:
        twisted.python.log.err()
        raise EmailSendException() from origException


class EmailAddressException(Exception):
    pass


class EmailSendException(Exception):
    pass
