# Copyright 2016 OpenMarket Ltd
# Copyright 2017 Vector Creations Ltd
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
from typing import TYPE_CHECKING, Dict, Optional

import phonenumbers

from sydent.db.valsession import ThreePidValSessionStore
from sydent.sms.openmarket import OpenMarketSMS
from sydent.util import time_msec
from sydent.validators import DestinationRejectedException, common

if TYPE_CHECKING:
    from sydent.sydent import Sydent

logger = logging.getLogger(__name__)


class MsisdnValidator:
    def __init__(self, sydent: "Sydent") -> None:
        self.sydent = sydent
        self.omSms = OpenMarketSMS(sydent)

        # cache originators & sms rules from config file
        self.originators = self.sydent.config.sms.originators
        self.smsRules = self.sydent.config.sms.smsRules

    async def requestToken(
        self,
        phoneNumber: phonenumbers.PhoneNumber,
        clientSecret: str,
        send_attempt: int,
        brand: Optional[str] = None,
    ) -> int:
        """
        Creates or retrieves a validation session and sends an text message to the
        corresponding phone number address with a token to use to verify the association.

        :param phoneNumber: The phone number to send the email to.
        :param clientSecret: The client secret to use.
        :param send_attempt: The current send attempt.
        :param brand: A hint at a brand from the request.

        :return: The ID of the session created (or of the existing one if any)
        """
        if str(phoneNumber.country_code) in self.smsRules:
            action = self.smsRules[str(phoneNumber.country_code)]
            if action == "reject":
                raise DestinationRejectedException()

        valSessionStore = ThreePidValSessionStore(self.sydent)

        msisdn = phonenumbers.format_number(
            phoneNumber, phonenumbers.PhoneNumberFormat.E164
        )[1:]

        valSession, token_info = valSessionStore.getOrCreateTokenSession(
            medium="msisdn", address=msisdn, clientSecret=clientSecret
        )

        valSessionStore.setMtime(valSession.id, time_msec())

        if token_info.send_attempt_number >= send_attempt:
            logger.info(
                "Not texting code because current send attempt (%d) is not less than given send attempt (%s)",
                send_attempt,
                token_info.send_attempt_number,
            )
            return valSession.id

        smsBodyTemplate = self.sydent.config.sms.body_template
        originator = self.getOriginator(phoneNumber)

        logger.info(
            "Attempting to text code %s to %s (country %d) with originator %s",
            token_info.token,
            msisdn,
            phoneNumber.country_code,
            originator,
        )

        smsBody = smsBodyTemplate.format(token=token_info.token)

        await self.omSms.sendTextSMS(smsBody, msisdn, originator)

        valSessionStore.setSendAttemptNumber(valSession.id, send_attempt)

        return valSession.id

    def getOriginator(
        self, destPhoneNumber: phonenumbers.PhoneNumber
    ) -> Dict[str, str]:
        """
        Gets an originator for a given phone number.

        :param destPhoneNumber: The phone number to find the originator for.

        :return: The originator (a dict with a "type" key and a "text" key).
        """
        countryCode = str(destPhoneNumber.country_code)

        origs = [
            {
                "type": "alpha",
                "text": "Matrix",
            }
        ]
        if countryCode in self.originators:
            origs = self.originators[countryCode]
        elif "default" in self.originators:
            origs = self.originators["default"]

        # deterministically pick an originator from the list of possible
        # originators, so if someone requests multiple codes, they come from
        # a consistent number (if there's any chance that some originators are
        # more likley to work than others, we may want to change, but it feels
        # like this should be something other than just picking one randomly).
        msisdn = phonenumbers.format_number(
            destPhoneNumber, phonenumbers.PhoneNumberFormat.E164
        )[1:]
        return origs[sum(int(i) for i in msisdn) % len(origs)]

    def validateSessionWithToken(
        self, sid: int, clientSecret: str, token: str
    ) -> Dict[str, bool]:
        """
        Validates the session with the given ID.

        :param sid: The ID of the session to validate.
        :param clientSecret: The client secret to validate.
        :param token: The token to validate.

        :return: A dict with a "success" key which is True if the session
            was successfully validated, False otherwise.
        """
        return common.validateSessionWithToken(self.sydent, sid, clientSecret, token)
