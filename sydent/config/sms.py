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

from typing import Dict, List

from sydent.config._base import CONFIG_PARSER_DICT, BaseConfig


class SMSConfig(BaseConfig):
    def parse_config(self, cfg: CONFIG_PARSER_DICT) -> None:
        """
        Parse the sms section of the config

        :param cfg: the configuration to be parsed
        """
        config = cfg.get("sms", {})

        self.body_template = config.get("bodyTemplate", "Your code is {token}")

        # Make sure username and password are bytes otherwise we can't use them with
        # b64encode.
        self.api_username = config.get("username", "").encode("UTF-8")
        self.api_password = config.get("password", "").encode("UTF-8")

        self.originators: Dict[str, List[Dict[str, str]]] = {}
        self.smsRules = {}

        for opt in config.keys():
            if opt.startswith("originators."):
                country = opt.split(".")[1]
                rawVal = config.get(opt)
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
                action = config.get(opt)

                if action not in ["allow", "reject"]:
                    raise Exception(
                        "Invalid SMS rule action: %s, expecting 'allow' or 'reject'"
                        % action
                    )

                self.smsRules[country] = action
