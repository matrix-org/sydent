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

import logging
from six.moves import urllib

from sydent.db.valsession import ThreePidValSessionStore
from sydent.util.emailutils import sendEmail
from sydent.validators import common

from sydent.util import time_msec

logger = logging.getLogger(__name__)


class EmailValidator:
    def __init__(self, sydent):
        self.sydent = sydent

    def requestToken(self, emailAddress, clientSecret, sendAttempt, nextLink, ipaddress=None):
        """
        Creates or retrieves a validation session and sends an email to the corresponding
        email address with a token to use to verify the association.

        :param emailAddress: The email address to send the email to.
        :type emailAddress: unicode
        :param clientSecret: The client secret to use.
        :type clientSecret: unicode
        :param sendAttempt: The current send attempt.
        :type sendAttempt: int
        :param nextLink: The link to redirect the user to once they have completed the
            validation.
        :type nextLink: unicode
        :param ipaddress: The requester's IP address.
        :type ipaddress: str or None

        :return: The ID of the session created (or of the existing one if any)
        :rtype: int
        """
        valSessionStore = ThreePidValSessionStore(self.sydent)

        valSession = valSessionStore.getOrCreateTokenSession(medium=u'email', address=emailAddress,
                                                             clientSecret=clientSecret)

        valSessionStore.setMtime(valSession.id, time_msec())

        if int(valSession.sendAttemptNumber) >= int(sendAttempt):
            logger.info("Not mailing code because current send attempt (%d) is not less than given send attempt (%s)", int(sendAttempt), int(valSession.sendAttemptNumber))
            return valSession.id

        ipstring = ipaddress if ipaddress else u"an unknown location"

        substitutions = {
            'ipaddress': ipstring,
            'link': self.makeValidateLink(valSession, clientSecret, nextLink),
            'token': valSession.token,
        }
        logger.info(
            "Attempting to mail code %s (nextLink: %s) to %s",
            valSession.token, nextLink, emailAddress,
        )
        sendEmail(self.sydent, 'email.template', emailAddress, substitutions)

        valSessionStore.setSendAttemptNumber(valSession.id, sendAttempt)

        return valSession.id

    def makeValidateLink(self, valSession, clientSecret, nextLink):
        """
        Creates a validation link that can be sent via email to the user.

        :param valSession: The current validation session.
        :type valSession: sydent.validators.ValidationSession
        :param clientSecret: The client secret to include in the link.
        :type clientSecret: unicode
        :param nextLink: The link to redirect the user to once they have completed the
            validation.
        :type nextLink: unicode

        :return: The validation link.
        :rtype: unicode
        """
        base = self.sydent.cfg.get('http', 'client_http_base')
        link = "%s/_matrix/identity/api/v1/validate/email/submitToken?token=%s&client_secret=%s&sid=%d" % (
            base,
            urllib.parse.quote(valSession.token),
            urllib.parse.quote(clientSecret),
            valSession.id,
        )
        if nextLink:
            # manipulate the nextLink to add the sid, because
            # the caller won't get it until we send a response,
            # by which time we've sent the mail.
            if '?' in nextLink:
                nextLink += '&'
            else:
                nextLink += '?'
            nextLink += "sid=" + urllib.parse.quote(str(valSession.id))

            link += "&nextLink=%s" % (urllib.parse.quote(nextLink))
        return link

    def validateSessionWithToken(self, sid, clientSecret, token):
        """
        Validates the session with the given ID.

        :param sid: The ID of the session to validate.
        :type sid: unicode
        :param clientSecret: The client secret to validate.
        :type clientSecret: unicode
        :param token: The token to validate.
        :type token: unicode

        :return: A dict with a "success" key which is True if the session
            was successfully validated, False otherwise.
        :rtype: dict[str, bool]
        """
        return common.validateSessionWithToken(self.sydent, sid, clientSecret, token)
