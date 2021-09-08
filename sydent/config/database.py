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

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from configparser import ConfigParser


class DatabaseConfig:
    def parse_config(self, cfg: "ConfigParser") -> None:
        """
        Parse the database section of the config

        :param cfg: the configuration to be parsed
        """
        self.database_path = cfg.get("db", "db.file")

    def generate_config_section(
        self,
        db_path: str,
        **kwargs,
    ) -> str:
        """
        Generate the database config section

        :param db_path: The SQLite Database file for Sydent to use.
        ...
        :return: the yaml config section
        """

        return (
            """\
        ## Database ##

        # The path to the SQLite database file for Sydent to use.
        # It can be set to ':memory:' to use a temporary database
        # in RAM instead of on disk. Required.
        #
        database_path: %(db_path)s
        """
            % locals()
        )
