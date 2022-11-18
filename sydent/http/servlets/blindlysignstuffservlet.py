# Copyright 2016 OpenMarket Ltd
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
from typing import TYPE_CHECKING

import signedjson.key
import signedjson.sign
from twisted.web.server import Request

from sydent.db.invite_tokens import JoinTokenStore
from sydent.http.auth import authV2
from sydent.http.servlets import (
    MatrixRestError,
    SydentResource,
    get_args,
    jsonwrap,
    send_cors,
)
from sydent.types import JsonDict

if TYPE_CHECKING:
    from sydent.sydent import Sydent

logger = logging.getLogger(__name__)


class BlindlySignStuffServlet(SydentResource):
    isLeaf = True

    def __init__(self, syd: "Sydent", require_auth: bool = False) -> None:
        super().__init__()
        self.sydent = syd
        self.server_name = syd.config.general.server_name
        self.tokenStore = JoinTokenStore(syd)
        self.require_auth = require_auth

    @jsonwrap
    def render_POST(self, request: Request) -> JsonDict:
        send_cors(request)

        if self.require_auth:
            authV2(self.sydent, request)

        args = get_args(request, ("private_key", "token", "mxid"))

        private_key_base64 = args["private_key"]
        token = args["token"]
        mxid = args["mxid"]

        sender = self.tokenStore.getSenderForToken(token)
        if sender is None:
            raise MatrixRestError(404, "M_UNRECOGNIZED", "Didn't recognize token")

        to_sign = {
            "mxid": mxid,
            "sender": sender,
            "token": token,
        }
        try:
            private_key = signedjson.key.decode_signing_key_base64(
                "ed25519", "0", private_key_base64
            )
            signed: JsonDict = signedjson.sign.sign_json(
                to_sign, self.server_name, private_key
            )
        except Exception:
            logger.exception("signing failed")
            raise MatrixRestError(500, "M_UNKNOWN", "Internal Server Error")

        return signed

    def render_OPTIONS(self, request: Request) -> bytes:
        send_cors(request)
        return b""
