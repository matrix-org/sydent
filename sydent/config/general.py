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
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from configparser import ConfigParser

logger = logging.getLogger(__name__)


class GeneralConfig:
    def parse_config(self, cfg: "ConfigParser") -> None:
        """
        Parse the 'general' section of the config

        :param cfg: the configuration to be parsed
        """
        self.server_name = cfg.get("general", "server.name")
        if self.server_name == "":
            self.server_name = os.uname()[1]
            logger.warning(
                "You have not specified a server name. I have guessed that this server is called '%s' ."
                "If this is incorrect, you should edit 'general.server.name' in the config file."
                % (self.server_name,)
            )
