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

import logging
import socket
from typing import Optional

from sydent.config._base import CONFIG_PARSER_DICT, BaseConfig

logger = logging.getLogger(__name__)


class EmailConfig(BaseConfig):
    def parse_config(self, cfg: CONFIG_PARSER_DICT) -> None:
        """
        Parse the email section of the config

        :param cfg: the configuration to be parsed
        """
        config = cfg.get("email", {})

        # These two options are deprecated
        self.template: Optional[str] = config.get("email.template", None)
        if self.template is not None:
            logger.warning(
                "'email.template' is a deprecated option."
                " Please use 'templates.path' and 'brand.default' instead."
            )

        self.invite_template = config.get("email.invite_template", None)
        if self.invite_template is not None:
            logger.warning(
                "'email.invite_template' is a deprecated option."
                " Please use 'templates.path' and 'brand.default' instead."
            )

        # This isn't used anywhere...
        self.validation_subject = config.get("email.subject")

        if self.invite_template is not None:
            logger.warning(
                "'email.subject' is no longer a supported option."
            )

        # Interpolation is turned off for these two options
        # This allows them to use %(variable)s substitution without raising errors
        self.invite_subject = config.get(
            "email.invite.subject", "%(sender_display_name)s has invited you to chat"
        )
        self.invite_subject_space = config.get(
            "email.invite.subject_space",
            "%(sender_display_name)s has invited you to a space",
        )

        self.smtp_server = config.get("email.smtphost", "localhost")
        self.smtp_port = int(config.get("email.smtpport", "25"))
        self.smtp_username = config.get("email.smtpusername", "")
        self.smtp_password = config.get("email.smtppassword", "")
        self.tls_mode = config.get("email.tlsmode", "None")

        # This is the fully qualified domain name for SMTP HELO/EHLO
        self.host_name = config.get("email.hostname") or socket.getfqdn()
        self.sender = config.get("email.from", "Sydent <noreply@example.com>")

        self.default_web_client_location = config.get(
            "email.default_web_client_location", "https://app.element.io"
        )

        self.username_obfuscate_characters = int(
            config.get("email.third_party_invite_username_obfuscate_characters", "3")
        )

        self.domain_obfuscate_characters = int(
            config.get("email.third_party_invite_domain_obfuscate_characters", "3")
        )
