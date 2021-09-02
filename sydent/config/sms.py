import configparser

from sydent.config.server import BaseConfig


class SMSConfig(BaseConfig):
    def parse_legacy_config(self, cfg: configparser):
        self.body_template = cfg.get("sms", "bodyTemplate")
        self.api_username = cfg.get("sms", "username")
        self.api_password = cfg.get("sms", "password")