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

from configparser import ConfigParser
from typing import Optional

from sydent.config._base import BaseConfig


class HTTPConfig(BaseConfig):
    def parse_config(self, cfg: "ConfigParser") -> bool:
        """
        Parse the http section of the config

        :param cfg: the configuration to be parsed
        """
        # This option is deprecated
        self.verify_response_template = cfg.get(
            "http", "verify_response_template", fallback=None
        )

        self.client_bind_address = cfg.get("http", "clientapi.http.bind_address")
        self.client_port = cfg.getint("http", "clientapi.http.port")

        # internal port is allowed to be set to an empty string in the config
        internal_api_port = cfg.get("http", "internalapi.http.port")
        self.internal_bind_address = cfg.get(
            "http", "internalapi.http.bind_address", fallback="::1"
        )
        self.internal_port: Optional[int] = None
        if internal_api_port != "":
            self.internal_port = int(internal_api_port)

        self.cert_file = cfg.get("http", "replication.https.certfile")
        self.ca_cert_file = cfg.get("http", "replication.https.cacert")

        self.replication_bind_address = cfg.get(
            "http", "replication.https.bind_address"
        )
        self.replication_port = cfg.getint("http", "replication.https.port")

        self.obey_x_forwarded_for = cfg.getboolean("http", "obey_x_forwarded_for")

        self.verify_federation_certs = cfg.getboolean("http", "federation.verifycerts")

        self.server_http_url_base = cfg.get("http", "client_http_base")

        self.base_replication_urls = {}

        for section in cfg.sections():
            if section.startswith("peer."):
                # peer name is all the characters after 'peer.'
                peer = section[5:]
                if cfg.has_option(section, "base_replication_url"):
                    base_url = cfg.get(section, "base_replication_url")
                    self.base_replication_urls[peer] = base_url

        return False
