# Copyright 2022 The Matrix.org Foundation C.I.C.
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

from twisted.web.server import Request

from sydent.http.servlets import SydentResource, jsonwrap, send_cors
from sydent.types import JsonDict


class VersionsServlet(SydentResource):
    isLeaf = True

    @jsonwrap
    def render_GET(self, request: Request) -> JsonDict:
        """
        Return the supported Matrix versions.
        """
        send_cors(request)

        return {
            "versions": [
                "r0.1.0",
                "r0.2.0",
                "r0.2.1",
                "r0.3.0",
                "v1.1",
                "v1.2",
                "v1.3",
                "v1.4",
                "v1.5",
            ]
        }

    def render_OPTIONS(self, request: Request) -> bytes:
        send_cors(request)
        return b""
