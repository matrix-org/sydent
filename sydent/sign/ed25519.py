# -*- coding: utf-8 -*-

# Copyright 2014 matrix.org
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

import nacl.encoding
import nacl.signing
import nacl.exceptions

import logging

logger = logging.getLogger(__name__)

class SydentEd25519:
    def __init__(self, syd):
        self.sydent = syd

        skHex = self.sydent.cfg.get('crypto', 'ed25519.signingkey')
        if skHex != '':
            self.signing_key = nacl.signing.SigningKey(skHex, encoder=nacl.encoding.HexEncoder)
            self.signing_key.version = '0' # argh
        else:
            logger.info("This server does not yet have an ed25519 signing key. "+
                        "Creating one and saving it in the config file.")

            self.signing_key = nacl.signing.SigningKey.generate()
            self.signing_key.version = '0' # argh
            skHex = self.signing_key.encode(encoder=nacl.encoding.HexEncoder)
            self.sydent.cfg.set('crypto', 'ed25519.signingkey', skHex)
            self.sydent.save_config()
