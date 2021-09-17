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

import logging
import logging.handlers
import os
from configparser import DEFAULTSECT, ConfigParser, NoSectionError
from typing import Dict

from twisted.python import log

from sydent.config._base import CONFIG_PARSER_DICT, ConfigError
from sydent.config._configparser import SydentConfigParser
from sydent.config.crypto import CryptoConfig
from sydent.config.database import DatabaseConfig
from sydent.config.email import EmailConfig
from sydent.config.general import GeneralConfig
from sydent.config.http import HTTPConfig
from sydent.config.sms import SMSConfig

logger = logging.getLogger(__name__)


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

    def _parse_config(self, cfg: CONFIG_PARSER_DICT) -> None:
        """
        Run the parse_config method on each of the objects in
        self.config_sections

        :param cfg: the configuration to be parsed
        """
        for section in self.config_sections:
            section.parse_config(cfg)

    def _parse_from_sydent_config_parser(self, cfg: SydentConfigParser) -> None:
        """
        Parse the configuration from a SydentConfigParser object

        :param cfg: the configuration to be parsed
        """
        config_dict: CONFIG_PARSER_DICT = {}
        for section in cfg.sections():
            config_dict[section] = {}
            # Copy in any values that are in the DEFAULT section
            # This must be done first as they might be overwritten.
            # This is for legacy support.
            for key, val in cfg.items(DEFAULTSECT):
                config_dict[section][key] = val
            # Copy in the values set in this section
            for key, val in cfg.items(section):
                config_dict[section][key] = val

        self._parse_config(config_dict)

    def parse_config_file(
        self, config_file: str, skip_logging_setup: bool = False
    ) -> None:
        """
        Parse the given config from a filepath, populating missing items and
        sections. NOTE: this method also sets up logging.

        :param config_file: the file to be parsed
        """
        # If the config file doesn't exist, raise an error
        if not os.path.exists(config_file):
            raise ConfigError(f"Unable to find config file: {config_file}")

        cfg = SydentConfigParser()
        cfg.read(config_file)

        # Logging is configured in cfg, but these options must be parsed first
        # so that we can log while parsing the rest
        if not skip_logging_setup:
            setup_logging(cfg)

        self._parse_from_sydent_config_parser(cfg)

    def parse_config_dict(self, config_dict: Dict) -> None:
        """
        Parse the given config from a dictionary, populating missing items and sections

        :param config_dict: the configuration dictionary to be parsed
        """
        # This is only ever called by tests so don't configure logging
        # as tests do this themselves

        self._parse_config(config_dict)


def setup_logging(cfg: ConfigParser) -> None:
    """
    Setup logging using the options selected in the config

    :param cfg: the configuration
    """
    log_format = "%(asctime)s - %(name)s - %(lineno)d - %(levelname)s" " - %(message)s"
    formatter = logging.Formatter(log_format)

    try:
        # empty or unset log.path means log to stderr
        log_path = cfg.get("general", "log.path", fallback=None) or None
        # unset log.level means use default
        log_level = cfg.get("general", "log.level", fallback="INFO")
    except NoSectionError:
        log_path = None
        log_level = "INFO"

    if log_path is not None:
        handler: logging.StreamHandler = logging.handlers.TimedRotatingFileHandler(
            log_path, when="midnight", backupCount=365
        )
        handler.setFormatter(formatter)

    else:
        handler = logging.StreamHandler()

    handler.setFormatter(formatter)
    rootLogger = logging.getLogger("")
    rootLogger.setLevel(log_level)
    rootLogger.addHandler(handler)

    observer = log.PythonLoggingObserver()
    observer.start()
