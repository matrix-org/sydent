import logging
from configparser import ConfigParser

import nacl
import signedjson.key

from sydent.config._base import BaseConfig

logger = logging.getLogger(__name__)


class CryptoConfig(BaseConfig):
    def parse_config(self, cfg: ConfigParser):
        signing_key_str = cfg.get("crypto", "ed25519.signingkey")
        signing_key_parts = signing_key_str.split(" ")

        save_key = False

        if signing_key_str == "":
            logger.info(
                "This server does not yet have an ed25519 signing key. "
                + "Creating one and saving it in the config file."
            )

            self.signing_key = signedjson.key.generate_signing_key("0")

            save_key = True
        elif len(signing_key_parts) == 1:
            # old format key
            logger.info("Updating signing key format: brace yourselves")

            self.signing_key = nacl.signing.SigningKey(
                signing_key_str, encoder=nacl.encoding.HexEncoder
            )
            self.signing_key.version = "0"
            self.signing_key.alg = signedjson.key.NACL_ED25519

            save_key = True
        else:
            self.signing_key = signedjson.key.decode_signing_key_base64(
                signing_key_parts[0], signing_key_parts[1], signing_key_parts[2]
            )

        if save_key:
            signing_key_str = "%s %s %s" % (
                self.signing_key.alg,
                self.signing_key.version,
                signedjson.key.encode_signing_key_base64(self.signing_key),
            )
            cfg.set("crypto", "ed25519.signingkey", signing_key_str)
            self.update_cfg = True
