from configparser import ConfigParser
import logging
import os
from typing import Set
from jinja2.environment import Environment

from jinja2.loaders import FileSystemLoader

from sydent.util.ip_range import DEFAULT_IP_RANGE_BLACKLIST, generate_ip_set
from sydent.config._base import BaseConfig

logger = logging.getLogger(__name__)


class GeneralConfig(BaseConfig):
    def parse_legacy_config(self, cfg: ConfigParser):
        self.server_name = cfg.get("general", "server.name")
        if self.server_name == "":
            self.server_name = os.uname()[1]
            logger.warning(
                (
                    "You had not specified a server name. I have guessed that this server is called '%s' "
                    + "If this is incorrect, you should edit 'general.server.name' in the config file."
                )
                % (self.server_name,)
            )

        self.pidfile = cfg.get("general", "pidfile.path")

        self.terms_path = cfg.get("general", "terms.path")

        self.address_lookup_limit = cfg.getint("general", "address_lookup_limit")

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

        if cfg.has_option("general", "prometheus_port"):
            prometheus_port = cfg.getint("general", "prometheus_port")
            prometheus_addr = cfg.get("general", "prometheus_addr")

            import prometheus_client

            prometheus_client.start_http_server(
                port=prometheus_port,
                addr=prometheus_addr,
            )

        if cfg.has_option("general", "sentry_dsn"):
            sentry_dsn = cfg.get("general", "sentry_dsn")

            import sentry_sdk

            sentry_sdk.init(dsn=sentry_dsn)
            with sentry_sdk.configure_scope() as scope:
                scope.set_tag("sydent_server_name", self.server_name)

        self.enable_v1_associations = parse_legacy_cfg_bool(
            cfg.get("general", "enable_v1_associations")
        )

        self.delete_tokens_on_bind = parse_legacy_cfg_bool(
            cfg.get("general", "delete_tokens_on_bind")
        )

        ip_blacklist = set_from_comma_sep_string(
            cfg.get("general", "ip.blacklist")
        )
        if not ip_blacklist:
            ip_blacklist = DEFAULT_IP_RANGE_BLACKLIST

        ip_whitelist = set_from_comma_sep_string(
            cfg.get("general", "ip.whitelist")
        )

        self.ip_blacklist = generate_ip_set(ip_blacklist)
        self.ip_whitelist = generate_ip_set(ip_whitelist)


def set_from_comma_sep_string(rawstr: str) -> Set[str]:
    if rawstr == "":
        return set()
    return {x.strip() for x in rawstr.split(",")}


def parse_legacy_cfg_bool(value):
    return value.lower() == "true"