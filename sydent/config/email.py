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

import socket
from typing import Optional

from sydent.config._base import CONFIG_PARSER_DICT, BaseConfig


class EmailConfig(BaseConfig):
    def parse_config(self, cfg: CONFIG_PARSER_DICT) -> bool:
        """
        Parse the email section of the config

        :param cfg: the configuration to be parsed
        """
        config = cfg.get("email")

        # These two options are deprecated
        self.template: Optional[str] = config.get("email.template", None)

        self.invite_template = config.get("email.invite_template", None)

        # This isn't used anywhere...
        self.validation_subject = config.get("email.subject")

        # Interpolation is turned off for these two options
        # This allows them to use %(variable)s substitution without raising errors
        self.invite_subject = config.get("email.invite.subject")
        self.invite_subject_space = config.get("email.invite.subject_space")

        self.smtp_server = config.get("email.smtphost")
        self.smtp_port = config.get("email.smtpport")
        self.smtp_username = config.get("email.smtpusername")
        self.smtp_password = config.get("email.smtppassword")
        self.tls_mode = config.get("email.tlsmode")

        # This is the fully qualified domain name for SMTP HELO/EHLO
        self.host_name = config.get("email.hostname") or socket.getfqdn()

        self.sender = config.get("email.from")

        self.default_web_client_location = config.get(
            "email.default_web_client_location"
        )

        self.username_obfuscate_characters = int(
            config.get("email.third_party_invite_username_obfuscate_characters")
        )

        self.domain_obfuscate_characters = int(
            config.get("email.third_party_invite_domain_obfuscate_characters")
        )

        return False
