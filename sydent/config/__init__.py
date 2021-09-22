# Copyright 2019-2021 The Matrix.org Foundation C.I.C.
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

import copy
import logging
import logging.handlers
import os
from configparser import DEFAULTSECT, ConfigParser
from typing import Dict

from twisted.python import log

from sydent.config._base import CONFIG_PARSER_DICT
from sydent.config._configparser import SydentConfigParser
from sydent.config.crypto import CryptoConfig
from sydent.config.database import DatabaseConfig
from sydent.config.email import EmailConfig
from sydent.config.general import GeneralConfig
from sydent.config.http import HTTPConfig
from sydent.config.sms import SMSConfig

logger = logging.getLogger(__name__)

CONFIG_DEFAULTS = {
    "general": {
        "server.name": os.environ.get("SYDENT_SERVER_NAME", ""),
        "log.path": "",
        "log.level": "INFO",
        "pidfile.path": os.environ.get("SYDENT_PID_FILE", "sydent.pid"),
        "terms.path": "",
        "address_lookup_limit": "10000",  # Maximum amount of addresses in a single /lookup request
        # The root path to use for load templates. This should contain branded
        # directories. Each directory should contain the following templates:
        #
        # * invite_template.eml
        # * verification_template.eml
        # * verify_response_template.html
        "templates.path": "res",
        # The brand directory to use if no brand hint (or an invalid brand hint)
        # is provided by the request.
        "brand.default": "matrix-org",
        # The following can be added to your local config file to enable prometheus
        # support.
        # 'prometheus_port': '8080',  # The port to serve metrics on
        # 'prometheus_addr': '',  # The address to bind to. Empty string means bind to all.
        # The following can be added to your local config file to enable sentry support.
        # 'sentry_dsn': 'https://...'  # The DSN has configured in the sentry instance project.
        # Whether clients and homeservers can register an association using v1 endpoints.
        "enable_v1_associations": "true",
        "delete_tokens_on_bind": "true",
        # Prevent outgoing requests from being sent to the following blacklisted
        # IP address CIDR ranges. If this option is not specified or empty then
        # it defaults to private IP address ranges.
        #
        # The blacklist applies to all outbound requests except replication
        # requests.
        #
        # (0.0.0.0 and :: are always blacklisted, whether or not they are
        # explicitly listed here, since they correspond to unroutable
        # addresses.)
        "ip.blacklist": "",
        # List of IP address CIDR ranges that should be allowed for outbound
        # requests. This is useful for specifying exceptions to wide-ranging
        # blacklisted target IP ranges.
        #
        # This whitelist overrides `ip.blacklist` and defaults to an empty
        # list.
        "ip.whitelist": "",
    },
    "db": {
        "db.file": os.environ.get("SYDENT_DB_PATH", "sydent.db"),
    },
    "http": {
        "clientapi.http.bind_address": "::",
        "clientapi.http.port": "8090",
        "internalapi.http.bind_address": "::1",
        "internalapi.http.port": "",
        "replication.https.certfile": "",
        "replication.https.cacert": "",  # This should only be used for testing
        "replication.https.bind_address": "::",
        "replication.https.port": "4434",
        "obey_x_forwarded_for": "False",
        "federation.verifycerts": "True",
        # verify_response_template is deprecated, but still used if defined. Define
        # templates.path and brand.default under general instead.
        #
        # 'verify_response_template': 'res/verify_response_page_template',
        "client_http_base": "",
    },
    "email": {
        # email.template and email.invite_template are deprecated, but still used
        # if defined. Define templates.path and brand.default under general instead.
        #
        # 'email.template': 'res/verification_template.eml',
        # 'email.invite_template': 'res/invite_template.eml',
        "email.from": "Sydent Validation <noreply@{hostname}>",
        "email.subject": "Your Validation Token",
        "email.invite.subject": "%(sender_display_name)s has invited you to chat",
        "email.invite.subject_space": "%(sender_display_name)s has invited you to a space",
        "email.smtphost": "localhost",
        "email.smtpport": "25",
        "email.smtpusername": "",
        "email.smtppassword": "",
        "email.hostname": "",
        "email.tlsmode": "0",
        # The web client location which will be used if it is not provided by
        # the homeserver.
        #
        # This should be the scheme and hostname only, see res/invite_template.eml
        # for the full URL that gets generated.
        "email.default_web_client_location": "https://app.element.io",
        # When a user is invited to a room via their email address, that invite is
        # displayed in the room list using an obfuscated version of the user's email
        # address. These config options determine how much of the email address to
        # obfuscate. Note that the '@' sign is always included.
        #
        # If the string is longer than a configured limit below, it is truncated to that limit
        # with '...' added. Otherwise:
        #
        # * If the string is longer than 5 characters, it is truncated to 3 characters + '...'
        # * If the string is longer than 1 character, it is truncated to 1 character + '...'
        # * If the string is 1 character long, it is converted to '...'
        #
        # This ensures that a full email address is never shown, even if it is extremely
        # short.
        #
        # The number of characters from the beginning to reveal of the email's username
        # portion (left of the '@' sign)
        "email.third_party_invite_username_obfuscate_characters": "3",
        # The number of characters from the beginning to reveal of the email's domain
        # portion (right of the '@' sign)
        "email.third_party_invite_domain_obfuscate_characters": "3",
    },
    "sms": {
        "bodyTemplate": "Your code is {token}",
        "username": "",
        "password": "",
    },
    "crypto": {
        "ed25519.signingkey": "",
    },
}


class ConfigError(Exception):
    pass


class SydentConfig:
    """This is the class in charge of handling Sydent's configuration.
    Handling of each individual section is delegated to other classes
    stored in a `config_sections` list.

    To use this class, create a new object and then call one of
    `parse_config_file` or `parse_config_dict` before creating the
    Sydent object that uses it.
    """

    def __init__(self):
        self.general = GeneralConfig()
        self.database = DatabaseConfig()
        self.crypto = CryptoConfig()
        self.sms = SMSConfig()
        self.email = EmailConfig()
        self.http = HTTPConfig()

        self.config_sections = [
            self.general,
            self.database,
            self.crypto,
            self.sms,
            self.email,
            self.http,
        ]

    def _parse_config(self, cfg: CONFIG_PARSER_DICT) -> bool:
        """
        Run the parse_config method on each of the objects in
        self.config_sections

        :param cfg: the configuration to be parsed

        :return: whether or not the config file needs updating. This method CAN
            return True, but it *shouldn't*. Instead a ConfigError exception
            should be raised. This is left in for the soon to be deprecated way
            of generating config files.
        """
        needs_saving = False
        for section in self.config_sections:
            if section.parse_config(cfg):
                needs_saving = True

        return needs_saving

    def _parse_from_dict(self, cfg: CONFIG_PARSER_DICT) -> bool:
        """
        Parse the configuration from a dict

        :param cfg: the configuration to be parsed

        :return: whether or not the config file needs updating. This method CAN
            return True, but it *shouldn't*. Instead a ConfigError exception
            should be raised. This is left in for the soon to be deprecated way
            of generating config files.
        """
        return self._parse_config(cfg)

    def _parse_from_sydent_config_parser(self, cfg: SydentConfigParser) -> bool:
        """
        Parse the configuration from a SydentConfigParser object

        :param cfg: the configuration to be parsed

        :return: whether or not the config file needs updating. This method CAN
            return True, but it *shouldn't*. Instead a ConfigError exception
            should be raised. This is left in for the soon to be deprecated way
            of generating config files.
        """
        config_dict: CONFIG_PARSER_DICT = {}
        for section in cfg.sections():
            config_dict[section] = {}
            # Copy in any values that are in the DEFAULT section
            # This must be done first as they might be overwritten
            for key, val in cfg.items(DEFAULTSECT):
                config_dict[section][key] = val
            # Copy in the values set in this section
            for key, val in cfg.items(section):
                config_dict[section][key] = val

        return self._parse_from_dict(config_dict)

    def parse_config_file(
        self, config_file: str, skip_logging_setup: bool = False
    ) -> None:
        """
        Parse the given config from a filepath, populating missing items and
        sections. NOTE: this method also sets up logging.

        :param config_file: the file to be parsed
        """
        # If the config file doesn't exist, prepopulate the config object
        # with the defaults.
        new_config_file = not os.path.exists(config_file)

        cfg = SydentConfigParser()
        for sect, entries in CONFIG_DEFAULTS.items():
            cfg.add_section(sect)
            for k, v in entries.items():
                cfg.set(sect, k, v)
        cfg.read(config_file)

        # Logging is configured in cfg, but these options must be parsed first
        # so that we can log while parsing the rest
        if not skip_logging_setup:
            setup_logging(cfg)

        needs_updating = self._parse_from_sydent_config_parser(cfg)

        # Don't edit config file when starting Sydent unless it's the first run
        if new_config_file:
            fp = open(config_file, "w")
            cfg.write(fp)
            fp.close()
            exit(0)

        if needs_updating:
            # A more specific log message should have been given earlier
            logger.error("The config file needs updating")
            exit(1)

    def parse_config_dict(self, config_dict: Dict) -> None:
        """
        Parse the given config from a dictionary, populating missing items and sections

        :param config_dict: the configuration dictionary to be parsed
        """
        # Build a config dictionary from the defaults merged with the given dictionary
        config = copy.deepcopy(CONFIG_DEFAULTS)
        for section, section_dict in config_dict.items():
            if section not in config:
                config[section] = {}
            for option in section_dict.keys():
                config[section][option] = config_dict[section][option]

        # This is only ever called by tests so don't configure logging
        # as tests do this themselves

        self._parse_from_dict(config)


def setup_logging(cfg: ConfigParser) -> None:
    """
    Setup logging using the options selected in the config

    :param cfg: the configuration
    """
    log_format = "%(asctime)s - %(name)s - %(lineno)d - %(levelname)s" " - %(message)s"
    formatter = logging.Formatter(log_format)

    logPath = cfg.get("general", "log.path")
    if logPath != "":
        handler: logging.StreamHandler = logging.handlers.TimedRotatingFileHandler(
            logPath, when="midnight", backupCount=365
        )
        handler.setFormatter(formatter)

        def sighup(signum, stack):
            logger.info("Closing log file due to SIGHUP")
            handler.doRollover()
            logger.info("Opened new log file due to SIGHUP")

    else:
        handler = logging.StreamHandler()

    handler.setFormatter(formatter)
    rootLogger = logging.getLogger("")
    rootLogger.setLevel(cfg.get("general", "log.level"))
    rootLogger.addHandler(handler)

    observer = log.PythonLoggingObserver()
    observer.start()
