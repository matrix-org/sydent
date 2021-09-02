import configparser

from sydent.config.server import BaseConfig


class HTTPConfig(BaseConfig):
    def parse_legacy_config(self, cfg: configparser):
        self.client_bind_address = cfg.get("http", "clientapi.http.bind_address")
        self.client_port = cfg.get("http", "clientapi.http.port")

        self.internal_bind_address = cfg.get("http", "internalapi.http.bind_address")
        self.internal_port = cfg.get("http", "internalapi.http.port")

        self.cert_file = cfg.get("http", "replication.https.certfile")
        self.ca_cert_File = cfg.get("http", "replication.https.cacert")

        self.replication_bind_address = cfg.get(
            "http", "replication.https.bind_address"
        )
        self.replication_port = cfg.get("http", "replication.https.port")

        self.obey_x_forwarded_for = cfg.get("http", "obey_x_forwarded_for")

        self.verify_federation_certs = cfg.getboolean("http", "federation.verifycerts")

        self.verify_response_template = cfg.get("http", "verify_response_template")

        self.server_http_url_base = cfg.get("http", "client_http_base")