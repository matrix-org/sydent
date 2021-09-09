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

from configparser import NoOptionError
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from configparser import ConfigParser


class HTTPConfig:
    def parse_config(self, cfg: "ConfigParser") -> None:
        """
        Parse the http section of the config

        :param cfg: the configuration to be parsed
        """
        # This option is deprecated
        self.verify_response_template = None
        if cfg.has_option("http", "verify_response_template"):
            self.verify_response_template = cfg.get("http", "verify_response_template")

        self.client_bind_address = cfg.get("http", "clientapi.http.bind_address")
        self.client_port = cfg.getint("http", "clientapi.http.port")

        # internal port is allowed to be set to an empty string in the config
        self.internal_port = cfg.get("http", "internalapi.http.port")
        if self.internal_port:
            self.internal_api_enabled = True
            self.internal_port = int(self.internal_port)
            try:
                self.internal_bind_address = cfg.get(
                    "http", "internalapi.http.bind_address"
                )
            except NoOptionError:
                self.internal_bind_address = "::1"
        else:
            self.internal_api_enabled = False

        self.cert_file = cfg.get("http", "replication.https.certfile")
        self.ca_cert_File = cfg.get("http", "replication.https.cacert")

        self.replication_bind_address = cfg.get(
            "http", "replication.https.bind_address"
        )
        self.replication_port = cfg.getint("http", "replication.https.port")

        self.obey_x_forwarded_for = cfg.get("http", "obey_x_forwarded_for")

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

    def generate_config_section(
        self,
        server_name: str,
        **kwargs,
    ) -> str:
        """
        Generate the sms config section

        :return: the yaml config section
        """

        return (
            """\
        ## HTTP ##

        # The base url of Sydent. This should be of the form
        # `scheme://base.url.com/here`. Required.
        #
        server_base_url: https://%(server_name)s

        # Settings for the listening points for the various APIs
        #
        http_servers:
          # Settings for the client API.
          #
          client_api:
            # The local IPv4 or IPv6 address to which to bind. Defaults to '::1'.
            #
            #bind_address: 120.243.0.12
            # The port number on which to listen. Defaults to 8090.
            #
            #port: 8089

          # Settings for the replication API.
          #
          replication_api:
            # The local IPv4 or IPv6 address to which to bind.
            # Defaults to '::1'.
            #
            #bind_address: 120.243.0.12

            # The port number on which to listen. Defaults to 4434.
            #
            #port: 4433

            # The file path to a certificate and private key.
            #
            # This file should contain both the public certificate and the
            # private key used to generate it. Defaults to empty.
            #
            #cert_file: sydent_priv_key_and_cert.pem

            # A file containing root CA certificate. If this is specified then
            # certificates of other Sydent servers signed by this CA will be
            # trusted.
            #
            # This is useful for testing or when it's not practical to get the
            # client cert signed by a real root CA but should never be used on
            # a production server. Defaults to empty.
            #
            #ca_cert: my_local_ca.crt

          # Settings for the internal API.
          #
          # Enabling this allows for binding and unbinding between identifiers
          # and matrix IDs without any validation. This is open to abuse, so is
          # disabled by default, and when it is enabled, is available only on a
          # separate socket which is bound to `localhost` by default.
          #
          internal_api:
            # Whether or not to enable internal API. Defaults to 'false'.
            #
            #enabled: true

            # The local IPv4 or IPv6 address to which to bind.
            # Defaults to '::1'.
            #
            #bind_address: 192.168.0.18

            # The port number on which to listen. Defaults to 9090.
            #
            #port: 8091

        # Whether or not Sydent should pay attention to X-Forwarded-For
        # headers. Defaults to 'true'.
        #
        #obey_x_forwarded_for: false

        # Whether or not Sydent should verify the TLS certificates of
        # homeservers it communicates with. Defaults to 'true'.
        #
        #verify_homeserver_certs: false
        """
            % locals()
        )
