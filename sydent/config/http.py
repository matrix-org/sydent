from configparser import ConfigParser, NoOptionError

from sydent.config._base import BaseConfig


class HTTPConfig(BaseConfig):
    def parse_config(self, cfg: ConfigParser):
        self.client_bind_address = cfg.get("http", "clientapi.http.bind_address")
        self.client_port = cfg.get("http", "clientapi.http.port")
        if self.client_port:
            self.client_port = int(self.client_port)

        self.internal_port = cfg.get("http", "internalapi.http.port")
        if self.internal_port:
            self.internal_port = int(self.internal_port)
            try:
                self.internal_bind_address = cfg.get(
                    "http", "internalapi.http.bind_address"
                )
            except NoOptionError:
                self.internal_bind_address = "::1"

        self.cert_file = cfg.get("http", "replication.https.certfile")
        self.ca_cert_File = cfg.get("http", "replication.https.cacert")

        self.replication_bind_address = cfg.get(
            "http", "replication.https.bind_address"
        )
        self.replication_port = cfg.getint("http", "replication.https.port")
        if self.replication_port:
            self.replication_port = int(self.replication_port)

        self.obey_x_forwarded_for = cfg.get("http", "obey_x_forwarded_for")

        self.verify_federation_certs = cfg.getboolean("http", "federation.verifycerts")

        self.verify_response_template = None
        if cfg.has_option("http", "verify_response_template"):
            self.verify_response_template = cfg.get("http", "verify_response_template")

        self.server_http_url_base = cfg.get("http", "client_http_base")

        self.base_replecation_urls = {}

        for section in cfg.sections():
            if section.startswith("peer."):
                # peer name is all the characters after 'peer.'
                peer = section[5:]
                if cfg.has_option(section, "base_replication_url"):
                    base_url = cfg.get(section, "base_replication_url")
                    self.base_replecation_urls[peer] = base_url
