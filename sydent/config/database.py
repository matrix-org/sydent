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

import os

from sydent.config._base import CONFIG_PARSER_DICT, BaseConfig


class DatabaseConfig(BaseConfig):
    def parse_config(self, cfg: CONFIG_PARSER_DICT) -> None:
        """
        Parse the database section of the config

        :param cfg: the configuration to be parsed
        """
        config = cfg.get("db", {})

        self.database_path = config.get(
            "db.file", os.environ.get("SYDENT_DB_PATH", "sydent.db")
        )
