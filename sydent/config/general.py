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
from typing import TYPE_CHECKING, Set

from jinja2.environment import Environment
from jinja2.loaders import FileSystemLoader

from sydent.util.ip_range import DEFAULT_IP_RANGE_BLACKLIST, generate_ip_set

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
                "The path specified by 'general.templates.path' does not exist."
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

        self.prometheus_enabled = cfg.has_option("general", "prometheus_port")
        if self.prometheus_enabled:
            self.prometheus_port = cfg.getint("general", "prometheus_port")
            self.prometheus_addr = cfg.get("general", "prometheus_addr")

        self.sentry_enabled = cfg.has_option("general", "sentry_dsn")
        if self.sentry_enabled:
            self.sentry_dsn = cfg.get("general", "sentry_dsn")

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

    def generate_config_section(
        self,
        server_name: str,
        pid_file: str,
        template_dir_path: str,
        **kwargs,
    ) -> str:
        """
        Generate the' general' config section

        :return: the yaml config section
        """

        return (
            """\
        ## General ##

        # The name of the server. Required.
        #
        server_name: %(server_name)s

        # Settings for configuring logging.
        #
        logging:
          # The path of the file to write the logs to OR 'stderr' to
          # log to stderr. Defaults to 'stderr'.
          #
          #log_path: sydent.log

          # The log level to use. This can be set to any level used by the python
          # 'logging' module. Note: it should be in all caps. Defaults to 'INFO'
          #
          #log_level: DEBUG

        # The file to save Sydent's process ID (PID) to. Required.
        #
        pid_file: %(pid_file)s

        # The file where the terms and conditions are configured for Sydent.
        # Defaults to empty.
        #
        #terms_file: terms_and_conditions.yaml

        # The maximum number of addresses that someone can query in a single
        # /lookup request. Defaults to 10000.
        #
        #address_lookup_limit: 100

        # Whether clients and homeservers can register an association using v1
        # API endpoints. Defaults to 'true'.
        #
        #enable_v1_associations: false

        # Whether to delete invite tokens after successful binding has taken
        # place. Defaults to 'true'.
        #
        #delete_tokens_on_bind: false

        # Templating options. Sending a value for 'brand' to some API endpoints
        # allows for different email and http templates to be used. These
        # templates should be stored in a file structure like this:
        #
        # root_template_dir/
        #     brand1/
        #         invite_template.eml
        #         verification_template.eml
        #         verify_response_template.html
        #     brand2/
        #         invite_template.eml
        #         verification_template.eml
        #         verify_response_template.html
        #
        templates:
          # The path of the root directory where template files are kept.
          # Required.
          #
          root_directory: %(template_dir_path)s

          # TThe brand directory to use if no brand (or an invalid brand)
          # is provided by the request. Defaults to 'matrix-org'.
          #
          #default_brand: awesome-brand-name

        # Settings for the prometheus metrics client
        #
        prometheus:
          # Whether or not to enable prometheus. Defaults to 'false'.
          #
          #enabled: true

          # The local IPv4 or IPv6 address to which to bind. Empty string
          # means bind to all. Defaults to empty.
          #
          #bind_address: 192.168.0.18

          # The port number on which to listen. Defaults to 8080.
          #
          #port: 8079

        # Settings for Sentry integration
        #
        sentry:
          # Whether of not to enable Sentry. Defaults to 'false'.
          #
          #enabled: true

          # The Sentry Data Source Name (DSN) to use. Defaults to empty.
          #
          #dsn: https://public_key@sentry.example.com/1

        # Settings for filtering outgoing requests based on the destination
        # IP address.
        #
        ip_filtering:
          # A list of CIDR IP address ranges to block outbound requests to.
          # Defaults to a list of private IP ranges to prevent DNS rebinding
          # attacks. This list can be found in 'sydent/util/ip_range.py'.
          #
          #blacklist:
          #  - "::1/128"
          #  - "fe80::/10"
          #  - "fc00::/7"
          #  - "2001:db8::/32"
          #  - "ff00::/8"
          #  - "fec0::/10"

          # List of IP address CIDR ranges that should be allowed for outbound
          # requests. This is useful for specifying exceptions to wide-ranging
          # blacklisted target IP ranges. This list overrides the blaclist.
          # Defaults to empty.
          #
          #whitelist:
          #  - 192.168.0.23
          #  - 202.31.555.2
        """
            % locals()
        )


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
