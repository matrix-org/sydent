import configparser
from typing import Dict, List

from sydent.config._base import BaseConfig


class SMSConfig(BaseConfig):
    def parse_legacy_config(self, cfg: configparser):
        self.body_template = cfg.get("sms", "bodyTemplate")
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
