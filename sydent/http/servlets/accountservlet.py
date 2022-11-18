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

from typing import TYPE_CHECKING

from twisted.web.server import Request

from sydent.http.auth import authV2
from sydent.http.servlets import SydentResource, jsonwrap, send_cors
from sydent.types import JsonDict

if TYPE_CHECKING:
    from sydent.sydent import Sydent


class AccountServlet(SydentResource):
    isLeaf = False

    def __init__(self, syd: "Sydent") -> None:
        super().__init__()
        self.sydent = syd

    @jsonwrap
    def render_GET(self, request: Request) -> JsonDict:
        """
        Return information about the user's account
        (essentially just a 'who am i')
        """
        send_cors(request)

        account = authV2(self.sydent, request)

        return {
            "user_id": account.userId,
        }

    def render_OPTIONS(self, request: Request) -> bytes:
        send_cors(request)
        return b""
