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
from configparser import ConfigParser
from typing import Set

from jinja2.environment import Environment
from jinja2.loaders import FileSystemLoader

from sydent.util.ip_range import DEFAULT_IP_RANGE_BLACKLIST, generate_ip_set

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
                "You have not specified a server name. I have guessed that this server is called '%s'. "
                "If this is incorrect, you should edit 'general.server.name' in the config file."
                % (self.server_name,)
            )

        # Get the possible brands by looking at directories under the
        # templates.path directory.
        self.templates_path = cfg.get("general", "templates.path")
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
            loader=FileSystemLoader(cfg.get("general", "templates.path")),
            autoescape=True,
        )

        self.default_brand = cfg.get("general", "brand.default")

        self.pidfile = cfg.get("general", "pidfile.path")

        self.terms_path = cfg.get("general", "terms.path")

        self.address_lookup_limit = cfg.getint("general", "address_lookup_limit")

        self.prometheus_port = cfg.getint("general", "prometheus_port", fallback=None)
        self.prometheus_addr = cfg.get("general", "prometheus_addr", fallback=None)
        self.prometheus_enabled = (
            self.prometheus_port is not None and self.prometheus_addr is not None
        )

        self.sentry_enabled = cfg.has_option("general", "sentry_dsn")
        self.sentry_dsn = self.sentry_dsn = cfg.get(
            "general", "sentry_dsn", fallback=None
        )

        self.enable_v1_associations = parse_cfg_bool(
            cfg.get("general", "enable_v1_associations")
        )

        self.delete_tokens_on_bind = parse_cfg_bool(
            cfg.get("general", "delete_tokens_on_bind")
        )

        ip_blacklist = set_from_comma_sep_string(cfg.get("general", "ip.blacklist"))
        if not ip_blacklist:
            ip_blacklist = DEFAULT_IP_RANGE_BLACKLIST

        ip_whitelist = set_from_comma_sep_string(cfg.get("general", "ip.whitelist"))

        self.ip_blacklist = generate_ip_set(ip_blacklist)
        self.ip_whitelist = generate_ip_set(ip_whitelist)


def set_from_comma_sep_string(rawstr: str) -> Set[str]:
    """
    Parse the a comma seperated string into a set

    :param rawstr: the string to be parsed
    """
    if rawstr == "":
        return set()
    return {x.strip() for x in rawstr.split(",")}


def parse_cfg_bool(value: str):
    """
    Parse a string config option into a boolean
    This method ignores capitalisation

    :param value: the string to be parsed
    """
    return value.lower() == "true"
