# Copyright 2021 The Matrix.org Foundation C.I.C.
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

from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from configparser import ConfigParser


class SMSConfig:
    def parse_config(self, cfg: "ConfigParser") -> None:
        """
        Parse the sms section of the config

        :param cfg: the configuration to be parsed
        """
        self.body_template = cfg.get("sms", "bodyTemplate")

        # Make sure username and password are bytes otherwise we can't use them with
        # b64encode.
        self.api_username = cfg.get("sms", "username").encode("UTF-8")
        self.api_password = cfg.get("sms", "password").encode("UTF-8")

        self.originators: Dict[str, List[Dict[str, str]]] = {}
        self.smsRules = {}

        for opt in cfg.options("sms"):
            if opt.startswith("originators."):
                country = opt.split(".")[1]
                rawVal = cfg.get("sms", opt)
                rawList = [i.strip() for i in rawVal.split(",")]

                self.originators[country] = []
                for origString in rawList:
                    parts = origString.split(":")
                    if len(parts) != 2:
                        raise Exception(
                            "Originators must be in form: long:<number>, short:<number> or alpha:<text>, separated by commas"
                        )
                    if parts[0] not in ["long", "short", "alpha"]:
                        raise Exception(
                            "Invalid originator type: valid types are long, short and alpha"
                        )
                    self.originators[country].append(
                        {
                            "type": parts[0],
                            "text": parts[1],
                        }
                    )
            elif opt.startswith("smsrule."):
                country = opt.split(".")[1]
                action = cfg.get("sms", opt)

                if action not in ["allow", "reject"]:
                    raise Exception(
                        "Invalid SMS rule action: %s, expecting 'allow' or 'reject'"
                        % action
                    )

                self.smsRules[country] = action

    def generate_config_section(
        self,
        **kwargs,
    ) -> str:
        """
        Generate the sms config section

        :return: the yaml config section
        """

        return """\
        ## SMS ##

        # Settings to do with sending SMS validation texts
        #
        sms:
          # The template to use for SMS validation texts. The string '{token}'
          # will get replaced with the validation code.
          # Defaults to 'Your code is {token}'.
          #
          #SMS_template: Your validation code is {token}

          # Settings to connect to the OpenMarket SMS sender at
          # https://smsc.openmarket.com/sms/v4/mt
          #
          openmarket_SMS_API:
            # Username for the service. Defaults to empty.
            #
            #username: myusername

            # Password for the service. Defaults to empty.
            #
            #password: mypassword

          # Settings for the SMS originators based on country code
          # An originator should be of the form '<long|short|alpha>:<originator>'
          # e.g 'alpha:Matrix' or 'short:012345'
          #
          sms_originator:
              # The list of originators to use by country code of the SMS
              # recipient. The originator is chosend deterministically from
              # this list so if someone requests multiple codes, they come
              # from a consistent number. Defaults to empty.
              #
              #country_code:
              #  - 1: # US/Canada
              #    - long:12125552368
              #    - long:12125552369
              #  - 44: # UK
              #    - short:12345

              # The default originator to use if nothing has been set for
              # the country code of the SMS recipient. Defaults to 'alpha:Sydent'
              #
              #default: alpha:Matrix

          # A blacklist of SMS recipient country codes. Verification texts
          # to numbers in these countries will not be sent. Default to empty.
          #
          #country_code_blacklist:
          #  - 44 # UK
          #  - 33 # France
          #  - 276 # Germany
        """
