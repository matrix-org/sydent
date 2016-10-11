# -*- coding: utf-8 -*-

# Copyright 2016 OpenMarket Ltd
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
import urllib

from sydent.db.valsession import ThreePidValSessionStore
from sydent.validators import ValidationSession
from sydent.sms.openmarket import OpenMarketSMS

from sydent.util import time_msec

from sydent.validators import IncorrectClientSecretException, SessionExpiredException

logger = logging.getLogger(__name__)


class MsisdnValidator:
    def __init__(self, sydent):
        self.sydent = sydent
        self.omSms = OpenMarketSMS(sydent)

    def requestToken(self, msisdn, clientSecret, sendAttempt, nextLink):
        valSessionStore = ThreePidValSessionStore(self.sydent)

        valSession = valSessionStore.getOrCreateTokenSession(
            medium='msisdn', address=msisdn, clientSecret=clientSecret
        )

        valSessionStore.setMtime(valSession.id, time_msec())

        if int(valSession.sendAttemptNumber) >= int(sendAttempt):
            logger.info("Not texting code because current send attempt (%d) is not less than given send attempt (%s)", int(sendAttempt), int(valSession.sendAttemptNumber))
            return valSession.id

        #substitutions = {
        #    'token': valSession.token,
        #}
        logger.info(
            "Attempting to text code %s to %s",
            valSession.token, msisdn,
        )
        self.omSms.sendTextSMS("Your code is " + valSession.token, msisdn)

        valSessionStore.setSendAttemptNumber(valSession.id, sendAttempt)

        return valSession.id

