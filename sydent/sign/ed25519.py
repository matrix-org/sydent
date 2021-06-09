# Copyright 2014 OpenMarket Ltd
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

import nacl.encoding
import nacl.exceptions
import nacl.signing
import signedjson.key

logger = logging.getLogger(__name__)


class SydentEd25519:
    def __init__(self, syd):
        self.sydent = syd

        save_key = False

        sk_str = self.sydent.cfg.get("crypto", "ed25519.signingkey")
        sk_parts = sk_str.split(" ")

        if sk_str == "":
            logger.info(
                "This server does not yet have an ed25519 signing key. "
                + "Creating one and saving it in the config file."
            )
            self.signing_key = signedjson.key.generate_signing_key("0")
            save_key = True
        elif len(sk_parts) == 1:
            # old format key
            logger.info("Updating signing key format: brace yourselves")
            self.signing_key = nacl.signing.SigningKey(
                sk_str, encoder=nacl.encoding.HexEncoder
            )
            self.signing_key.version = "0"
            self.signing_key.alg = signedjson.key.NACL_ED25519

            save_key = True
        else:
            self.signing_key = signedjson.key.decode_signing_key_base64(
                sk_parts[0], sk_parts[1], sk_parts[2]
            )

        if save_key:
            sk_str = "%s %s %s" % (
                self.signing_key.alg,
                self.signing_key.version,
                signedjson.key.encode_signing_key_base64(self.signing_key),
            )
            self.sydent.cfg.set("crypto", "ed25519.signingkey", sk_str)
            self.sydent.save_config()
            logger.info("Key saved")
