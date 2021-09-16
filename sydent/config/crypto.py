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

from sydent.config._base import BaseConfig

logger = logging.getLogger(__name__)


class CryptoConfig(BaseConfig):
    def parse_config(self, cfg: "ConfigParser") -> bool:
        """
        Parse the crypto section of the config
        :param cfg: the configuration to be parsed
        """

        signing_key_str = cfg.get("crypto", "ed25519.signingkey")
        signing_key_parts = signing_key_str.split(" ")

        if signing_key_str == "":
            logger.warning(
                "'ed25519.signingkey' cannot be blank. Please generate a new"
                " signing key with the 'generate-key' script."
            )

            self.signing_key = signedjson.key.generate_signing_key("0")

            return True
        elif len(signing_key_parts) == 1:
            # old format key
            logger.warning(
                "Updating signing key format for this run. Please run the"
                " 'update-key' script to speedup the next startup"
            )

            self.signing_key = nacl.signing.SigningKey(
                signing_key_str, encoder=nacl.encoding.HexEncoder
            )
            self.signing_key.version = "0"
            self.signing_key.alg = signedjson.key.NACL_ED25519
        else:
            self.signing_key = signedjson.key.decode_signing_key_base64(
                signing_key_parts[0], signing_key_parts[1], signing_key_parts[2]
            )

        return False
