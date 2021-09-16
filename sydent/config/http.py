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

from sydent.config._base import CONFIG_PARSER_DICT, BaseConfig


class HTTPConfig(BaseConfig):
    def parse_config(self, cfg: CONFIG_PARSER_DICT) -> bool:
        """
        Parse the http section of the config

        :param cfg: the configuration to be parsed
        """
        config = cfg.get("http")

        # This option is deprecated
        self.verify_response_template = config.get("verify_response_template") or None

        self.client_bind_address = config.get("clientapi.http.bind_address")
        self.client_port = int(config.get("clientapi.http.port"))

        # internal port is allowed to be set to an empty string in the config
        internal_api_port = config.get("internalapi.http.port") or None
        self.internal_bind_address = (
            config.get("internalapi.http.bind_address") or "::1"
        )

        if internal_api_port is not None:
            self.internal_api_enabled = True
            self.internal_port = int(internal_api_port)
        else:
            self.internal_api_enabled = False

        self.cert_file = config.get("replication.https.certfile")
        self.ca_cert_file = config.get("replication.https.cacert")

        self.replication_bind_address = config.get("replication.https.bind_address")
        self.replication_port = int(config.get("replication.https.port"))

        self.obey_x_forwarded_for = cfg.getboolean("http", "obey_x_forwarded_for")

        self.verify_federation_certs = bool(config.get("federation.verifycerts"))

        self.server_http_url_base = config.get("client_http_base")

        self.base_replication_urls = {}

        for section in cfg.keys():
            if section.startswith("peer."):
                # peer name is all the characters after 'peer.'
                peer = section[5:]
                peer_config = cfg.get(section)
                if "base_replication_url" in peer_config.keys():
                    base_url = peer_config.get("base_replication_url")
                    self.base_replication_urls[peer] = base_url

        return False
