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

from configparser import ConfigParser
from typing import Dict, List

from sydent.config._base import BaseConfig
from sydent.config.exceptions import ConfigError


class SMSConfig(BaseConfig):
    def parse_config(self, cfg: "ConfigParser") -> bool:
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
                        raise ConfigError(
                            "Originators must be in form: long:<number>, short:<number> or alpha:<text>, separated by commas"
                        )
                    if parts[0] not in ["long", "short", "alpha"]:
                        raise ConfigError(
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
                    raise ConfigError(
                        "Invalid SMS rule action: %s, expecting 'allow' or 'reject'"
                        % action
                    )

                self.smsRules[country] = action

        self.msisdn_ratelimit_burst = cfg.getint(
            "sms", "msisdn.ratelimit.burst", fallback=5
        )
        self.msisdn_ratelimit_rate_hz = cfg.getfloat(
            "sms", "msisdn.ratelimit.rate_hz", fallback=1.0 / (60.0 * 60.0)
        )

        self.country_ratelimit_burst = cfg.getint(
            "sms", "country.ratelimit.burst", fallback=50
        )
        self.country_ratelimit_rate_hz = cfg.getfloat(
            "sms", "country.ratelimit.rate_hz", fallback=1.0 / 60.0
        )

        return False
