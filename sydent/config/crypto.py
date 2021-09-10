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
from configparser import ConfigParser

import nacl
import signedjson.key

logger = logging.getLogger(__name__)


class CryptoConfig:
    def parse_config(self, cfg: "ConfigParser") -> None:
        """
        Parse the crypto section of the config
        :param cfg: the configuration to be parsed
        """

        signing_key_str = cfg.get("crypto", "ed25519.signingkey")
        signing_key_parts = signing_key_str.split(" ")

        self.save_key = False

        if signing_key_str == "":
            logger.info(
                "This server does not yet have an ed25519 signing key. "
                "Creating one and saving it in the config file."
            )

            self.signing_key = signedjson.key.generate_signing_key("0")

            self.save_key = True
        elif len(signing_key_parts) == 1:
            # old format key
            logger.info("Updating signing key format: brace yourselves")

            self.signing_key = nacl.signing.SigningKey(
                signing_key_str, encoder=nacl.encoding.HexEncoder
            )
            self.signing_key.version = "0"
            self.signing_key.alg = signedjson.key.NACL_ED25519

            self.save_key = True
        else:
            self.signing_key = signedjson.key.decode_signing_key_base64(
                signing_key_parts[0], signing_key_parts[1], signing_key_parts[2]
            )

        if self.save_key:
            signing_key_str = "%s %s %s" % (
                self.signing_key.alg,
                self.signing_key.version,
                signedjson.key.encode_signing_key_base64(self.signing_key),
            )
            cfg.set("crypto", "ed25519.signingkey", signing_key_str)
