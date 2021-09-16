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

from abc import ABC, abstractmethod
from typing import Dict

# The type of dict that the SydentConfigParser object get's converted into
CONFIG_PARSER_DICT = Dict[str, Dict[str, str]]


class BaseConfig(ABC):
    @abstractmethod
    def parse_config(self, cfg: CONFIG_PARSER_DICT) -> bool:
        """
        Parse the a section of the config

        :param cfg: the configuration to be parsed

        :return: whether or not cfg has been altered. This method CAN
            return True, but it *shouldn't* as this leads to altering the
            config file.
        """
        pass


def parse_cfg_bool(value: str):
    """
    Parse a string config option into a boolean
    This method ignores capitalisation

    :param value: the string to be parsed
    """
    return value.lower() == "true"
