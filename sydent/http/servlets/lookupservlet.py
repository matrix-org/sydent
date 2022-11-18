# Copyright 2014,2017 OpenMarket Ltd
# Copyright 2019 The Matrix.org Foundation C.I.C.
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

import signedjson.sign
from twisted.web.server import Request

from sydent.db.threepid_associations import GlobalAssociationStore
from sydent.http.servlets import SydentResource, get_args, jsonwrap, send_cors
from sydent.types import JsonDict
from sydent.util import json_decoder

if TYPE_CHECKING:
    from sydent.sydent import Sydent

logger = logging.getLogger(__name__)


class LookupServlet(SydentResource):
    isLeaf = True

    def __init__(self, syd: "Sydent") -> None:
        super().__init__()
        self.sydent = syd

    @jsonwrap
    def render_GET(self, request: Request) -> JsonDict:
        """
        Look up an individual threepid.

        ** DEPRECATED **

        Params: 'medium': the medium of the threepid
                'address': the address of the threepid
        Returns: A signed association if the threepid has a corresponding mxid, otherwise the empty object.
        """
        send_cors(request)

        args = get_args(request, ("medium", "address"))

        medium = args["medium"]
        address = args["address"]

        globalAssocStore = GlobalAssociationStore(self.sydent)

        sgassoc_raw = globalAssocStore.signedAssociationStringForThreepid(
            medium, address
        )

        if not sgassoc_raw:
            return {}

        # TODO validate this really is a dict
        sgassoc: JsonDict = json_decoder.decode(sgassoc_raw)
        if self.sydent.config.general.server_name not in sgassoc["signatures"]:
            # We have not yet worked out what the proper trust model should be.
            #
            # Maybe clients implicitly trust a server they talk to (and so we
            # should sign every assoc we return as ourselves, so they can
            # verify this).
            #
            # Maybe clients really want to know what server did the original
            # verification, and want to only know exactly who signed the assoc.
            #
            # Until we work out what we should do, sign all assocs we return as
            # ourself. This is vaguely ok because there actually is only one
            # identity server, but it happens to have two names (matrix.org and
            # vector.im), and so we're not really lying too much.
            #
            # We do this when we return assocs, not when we receive them over
            # replication, so that we can undo this decision in the future if
            # we wish, without having destroyed the raw underlying data.
            sgassoc = signedjson.sign.sign_json(
                sgassoc,
                self.sydent.config.general.server_name,
                self.sydent.keyring.ed25519,
            )
        return sgassoc

    def render_OPTIONS(self, request: Request) -> bytes:
        send_cors(request)
        return b""
