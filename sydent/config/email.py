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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from configparser import ConfigParser


class EmailConfig:
    def parse_config(self, cfg: "ConfigParser") -> None:
        """
        Parse the email section of the config

        :param cfg: the configuration to be parsed
        """

        # These two options are deprecated
        self.template = None
        if cfg.has_option("email", "email.template"):
            self.template = cfg.get("email", "email.template")

        self.invite_template = None
        if cfg.has_option("email", "email.invite_template"):
            self.invite_template = cfg.get("email", "email.invite_template")

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

        self.default_web_client_location = cfg.get(
            "email", "email.default_web_client_location"
        )

        self.username_obfuscate_characters = cfg.getint(
            "email", "email.third_party_invite_username_obfuscate_characters"
        )

        self.domain_obfuscate_characters = cfg.getint(
            "email", "email.third_party_invite_domain_obfuscate_characters"
        )

    def generate_config_section(
        self,
        **kwargs,
    ) -> str:
        """
        Generate the email config section

        :return: the yaml config section
        """

        return """\
        ## Emails ##

        # Email settings
        #
        email:
          # SMTP server settings
          #
          SMTP:
            # The address of the SMTP server. Defaults to 'localhost'.
            #
            #server: smtp.myemailsender.com

            # The port to connect to the server on. Defaults to 25.
            #
            #port: 587

            # The username for the SMTP server. Defaults to empty.
            #
            #username: sydent@myemailsender.com

            # The password for the SMTP server. Defaults to empty.
            #
            #password: mypassword

            # The security mode to use. This can take one of the following
            # options:
            #
            # - None [Default]
            # - TLS
            # - SSL
            # - STARTTLS
            #
            #tls_mode: TLS

            # The fully qualified domain name (FQDN) to use with HELO/EHLO
            # command. Defaults to domain name configured for local host.
            #
            #host_name: sydent.myserver.com

          # Settings that affect the contents of Sydent's emails.
          #
          # Some of these settings are string templates and can take advantage
          # of Sydent's string substitutions. Any parameters set in the body of
          # a request to `/_matrix/identity/v2/store-invite` can be used. These
          # may include the following:
          #
          # room_name           - The name of the room to which the user is
          #                       invited.
          #
          # room_alias          - The cannonical room alias for the room to
          #                       which the user is invited.
          #
          # sender_display_name - The display name of the user ID initiating
          #                       the invite.
          #
          # For more options see https://matrix.org/docs/spec/identity_service/latest
          #
          # For example '%(room_alias)s' in a string template will be replaced by
          # the value set for room_alias
          #
          contents:
            # The email address that should appear to have been sent from. This
            # should take the form: 'Display Name Here <actual.email@example.com>'
            #
            # Defaults to 'Sydent <noreply@example.com>'.
            #
            #sender: Server Name <noreply@example.com>

            # The subject line of emails that invite someone to a room. This is
            # a string template.
            #
            # Defaults to '%(sender_display_name)s has invited you to chat'.
            #
            #room_invite_subject: Invitation to %(room_alias)s

            # The subject line of emails that invite someone to a space. This is
            # a string template.
            #
            # Defaults to '%(sender_display_name)s has invited you to a space'.
            #
            #space_invite_subject: Invitation to %(room_alias)s

            # The web client location which will be used if one is not provided by
            # the homeserver. This should be of the form 'scheme://base.url.com/here'
            #
            # A homeserver can provide a default client by sending a value for
            # 'org.matrix.web_client_location' in the request to '/store-invite'.
            #
            # Defaults to 'https://app.element.io'.
            #
            #default_matrix_client: https://fluffychat.im/web

            # When a user is invited to a room via their email address, that invite is
            # displayed in the room list using an obfuscated version of the user's email
            # address. These config options determine how much of the email address to
            # obfuscate. Note that the '@' sign is always included.
            #
            # If the string is longer than a configured limit below, it is truncated to
            # that limit with '...' added. For shorter strings, the following rules are
            # used:
            #
            # * If the string has more than 5 characters, it is truncated to 3 characters
            #   + '...' (e.g. 'username' would become 'use...')
            #
            # * If the string has between 2 and 5 characters inclusive, it is truncated
            #   to 1 character + '...' (e.g. 'user' would become 'u...')
            #
            # * If the string is 1 character long, it is converted to just '...'
            #   (e.g. 'a' would become '...')
            #
            # This ensures that a full email address is never shown, even if it is extremely
            # short.
            #
            obfuscation_amounts:
              # The number of characters from the beginning to reveal of the email's username
              # portion (left of the '@' sign). Defaults to 3.
              #
              #username: 5

              # The number of characters from the beginning to reveal of the email's domain
              # portion (right of the '@' sign). Defaults to 3.
              #
              #domain: 5
        """
