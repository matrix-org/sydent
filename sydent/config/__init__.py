# Copyright 2019 New Vector Ltd
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

from sydent.config.database import DatabaseConfig


class ConfigError(Exception):
    pass


class SydentConfig:
    """This is the class in charge of handling Sydent's configuration.
    Handling of each individual section is delegated to other classes
    stored in a `config_sections` list.
    """

    def __init__(self):
        self.database = DatabaseConfig()

        self.config_sections = [self.database]

    def _parse_config(self, cfg: ConfigParser) -> None:
        """
        Run the parse_config method on each of the objects in
        self.config_sections

        :param cfg: the configuration to be parsed
        """
        for section in self.config_sections:
            section.parse_config(cfg)

    def parse_from_config_parser(self, cfg: ConfigParser) -> None:
        """
        Parse the configuration from a ConfigParser object

        :param cfg: the configuration to be parsed
        """
        self._parse_config(cfg)
