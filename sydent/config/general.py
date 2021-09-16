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
from typing import List

from jinja2.environment import Environment
from jinja2.loaders import FileSystemLoader

from sydent.config._base import CONFIG_PARSER_DICT, BaseConfig
from sydent.util.ip_range import DEFAULT_IP_RANGE_BLACKLIST, generate_ip_set

logger = logging.getLogger(__name__)


class GeneralConfig(BaseConfig):
    def parse_config(self, cfg: CONFIG_PARSER_DICT) -> bool:
        """
        Parse the 'general' section of the config

        :param cfg: the configuration to be parsed
        """
        config = cfg.get("general")

        self.server_name = config.get("server.name") or None
        if self.server_name is None:
            self.server_name = os.uname()[1]
            logger.warning(
                "You have not specified a server name. I have guessed that this server is called '%s'. "
                "If this is incorrect, you should edit 'general.server.name' in the config file."
                % (self.server_name,)
            )

        # Get the possible brands by looking at directories under the
        # templates.path directory.
        self.templates_path = config.get("templates.path")
        if os.path.exists(self.templates_path):
            self.valid_brands = {
                p
                for p in os.listdir(self.templates_path)
                if os.path.isdir(os.path.join(self.templates_path, p))
            }
        else:
            logging.warning(
                f"The path specified by 'general.templates.path' ({self.templates_path}) does not exist."
            )
            # This is a legacy code-path and assumes that verify_response_template,
            # email.template, and email.invite_template are defined.
            self.valid_brands = set()

        self.template_environment = Environment(
            loader=FileSystemLoader(self.templates_path),
            autoescape=True,
        )

        self.default_brand = config.get("brand.default")

        self.pidfile = config.get("pidfile.path")

        self.terms_path = config.get("terms.path")

        self.address_lookup_limit = int(config.get("address_lookup_limit"))

        self.prometheus_port = config.get("prometheus_port") or None
        self.prometheus_addr = config.get("prometheus_addr") or None

        if self.prometheus_port is not None and self.prometheus_addr is not None:
            self.prometheus_enabled = True
            self.prometheus_port = int(self.prometheus_port)
        else:
            self.prometheus_enabled = False

        self.sentry_dsn = config.get("sentry_dsn") or None
        self.sentry_enabled = self.sentry_dsn is not None

        self.enable_v1_associations = parse_cfg_bool(
            config.get("enable_v1_associations") or ""
        )

        self.delete_tokens_on_bind = parse_cfg_bool(
            config.get("delete_tokens_on_bind") or ""
        )

        ip_blacklist = list_from_comma_sep_string(config.get("ip.blacklist") or "")
        if not ip_blacklist:
            ip_blacklist = DEFAULT_IP_RANGE_BLACKLIST

        ip_whitelist = list_from_comma_sep_string(config.get("ip.whitelist") or "")

        self.ip_blacklist = generate_ip_set(ip_blacklist)
        self.ip_whitelist = generate_ip_set(ip_whitelist)

        return False


def list_from_comma_sep_string(rawstr: str) -> List[str]:
    """
    Parse the a comma seperated string into a list

    :param rawstr: the string to be parsed
    """
    if rawstr == "":
        return []
    return [x.strip() for x in rawstr.split(",")]


def parse_cfg_bool(value: str):
    """
    Parse a string config option into a boolean
    This method ignores capitalisation

    :param value: the string to be parsed
    """
    return value.lower() == "true"
