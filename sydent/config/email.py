import socket
from configparser import ConfigParser

from sydent.config._base import BaseConfig


class EmailConfig(BaseConfig):
    def parse_legacy_config(self, cfg: ConfigParser):

        self.template = None
        if cfg.has_option("email", "email.template"):
            self.template = cfg.get("email", "email.template")

        self.invite_template = None
        if cfg.has_option("email", "email.invite_template"):
            self.invite_template = cfg.get("email", "email.invite_template")

        self.sender = cfg.get("email", "email.from")

        self.host_name = cfg.get("email", "email.hostname")
        if self.host_name == "":
            self.host_name = socket.getfqdn()

        # These are deprecated options as subject is now set by templates
        self.validation_subject = cfg.get("email", "email.subject")
        self.invite_subject = cfg.get("email", "email.invite.subject", raw=True)

        self.smtp_server = cfg.get("email", "email.smtphost")
        self.smtp_port = cfg.get("email", "email.smtpport")
        self.smtp_username = cfg.get("email", "email.smtpusername")
        self.smtp_password = cfg.get("email", "email.smtppassword")
        self.tls_mode = cfg.get("email", "email.tlsmode")

        self.default_web_client_location = cfg.get(
            "email", "email.default_web_client_location"
        )

        self.username_obfuscate_characters = cfg.getint(
            "email", "email.third_party_invite_username_obfuscate_characters"
        )

        self.domain_obfuscate_characters = cfg.getint(
            "email", "email.third_party_invite_domain_obfuscate_characters"
        )
