# Copyright 2017 OpenMarket Ltd
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

from twisted.web.server import Request

from sydent.db.threepid_associations import GlobalAssociationStore
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


class BulkLookupServlet(SydentResource):
    isLeaf = True

    def __init__(self, syd: "Sydent") -> None:
        super().__init__()
        self.sydent = syd

    @jsonwrap
    def render_POST(self, request: Request) -> JsonDict:
        """
        Bulk-lookup for threepids.
        Params: 'threepids': list of threepids, each of which is a list of medium, address
        Returns: Object with key 'threepids', which is a list of results where each result
                 is a 3 item list of medium, address, mxid
                 Note that results are not streamed to the client.
        Threepids for which no mapping is found are omitted.
        """
        send_cors(request)

        args = get_args(request, ("threepids",))

        threepids = args["threepids"]
        if not isinstance(threepids, list):
            raise MatrixRestError(400, "M_INVALID_PARAM", "threepids must be a list")

        logger.info("Bulk lookup of %d threepids", len(threepids))

        globalAssocStore = GlobalAssociationStore(self.sydent)
        results = globalAssocStore.getMxids(threepids)

        return {"threepids": results}

    def render_OPTIONS(self, request: Request) -> bytes:
        send_cors(request)
        return b""
