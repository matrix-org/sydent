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
from configparser import ConfigParser
from typing import Optional

from sydent.config._base import BaseConfig
from sydent.config.exceptions import ConfigError
from sydent.util.emailutils import EmailAddressException, check_valid_email_address


class EmailConfig(BaseConfig):
    def parse_config(self, cfg: ConfigParser) -> bool:
        """
        Parse the email section of the config

        :param cfg: the configuration to be parsed
        """

        # These two options are deprecated
        self.template: Optional[str] = cfg.get("email", "email.template", fallback=None)

        self.invite_template = cfg.get("email", "email.invite_template", fallback=None)

        # This isn't used anywhere...
        self.validation_subject = cfg.get("email", "email.subject")

        self.invite_subject = cfg.get("email", "email.invite.subject", raw=True)
        self.invite_subject_space = cfg.get(
            "email", "email.invite.subject_space", raw=True
        )

        self.smtp_server = cfg.get("email", "email.smtphost")
        self.smtp_port = cfg.get("email", "email.smtpport")
        self.smtp_username = cfg.get("email", "email.smtpusername")
        self.smtp_password = cfg.get("email", "email.smtppassword")
        self.tls_mode = cfg.get("email", "email.tlsmode")

        # This is the fully qualified domain name for SMTP HELO/EHLO
        self.host_name = cfg.get("email", "email.hostname")
        if self.host_name == "":
            self.host_name = socket.getfqdn()

        self.sender = cfg.get("email", "email.from")
        try:
            check_valid_email_address(self.sender, allow_description=True)
        except EmailAddressException as e:
            raise ConfigError(f"Invalid email address '{self.sender}'") from e

        self.default_web_client_location = cfg.get(
            "email", "email.default_web_client_location"
        )

        self.username_obfuscate_characters = cfg.getint(
            "email", "email.third_party_invite_username_obfuscate_characters"
        )

        self.domain_obfuscate_characters = cfg.getint(
            "email", "email.third_party_invite_domain_obfuscate_characters"
        )

        third_party_invite_homeserver_blocklist = cfg.get(
            "email", "email.third_party_invite_homeserver_blocklist", fallback=""
        )
        third_party_invite_room_blocklist = cfg.get(
            "email", "email.third_party_invite_room_blocklist", fallback=""
        )
        third_party_invite_keyword_blocklist = cfg.get(
            "email", "email.third_party_invite_keyword_blocklist", fallback=""
        )
        self.third_party_invite_homeserver_blocklist = {
            server
            for server in third_party_invite_homeserver_blocklist.split("\n")
            if server  # filter out empty lines
        }
        self.third_party_invite_room_blocklist = {
            room_id
            for room_id in third_party_invite_room_blocklist.split("\n")
            if room_id  # filter out empty lines
        }
        self.third_party_invite_keyword_blocklist = {
            keyword.casefold()
            for keyword in third_party_invite_keyword_blocklist.split("\n")
            if keyword
        }

        self.email_sender_ratelimit_burst = cfg.getint(
            "email", "email.ratelimit_sender.burst", fallback=5
        )
        self.email_sender_ratelimit_rate_hz = cfg.getfloat(
            "email", "email.ratelimit_sender.rate_hz", fallback=1.0 / (5 * 60.0)
        )

        return False
