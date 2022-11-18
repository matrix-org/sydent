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
import urllib
from http import HTTPStatus
from json import JSONDecodeError
from typing import TYPE_CHECKING, Dict

from twisted.internet.error import ConnectError, DNSLookupError
from twisted.web.client import ResponseFailed
from twisted.web.server import Request

from sydent.http.httpclient import FederationHttpClient
from sydent.http.servlets import SydentResource, asyncjsonwrap, get_args, send_cors
from sydent.types import JsonDict
from sydent.users.tokens import issueToken
from sydent.util.stringutils import is_valid_matrix_server_name

if TYPE_CHECKING:
    from sydent.sydent import Sydent

logger = logging.getLogger(__name__)


class RegisterServlet(SydentResource):
    isLeaf = True

    def __init__(self, syd: "Sydent") -> None:
        super().__init__()
        self.sydent = syd
        self.client = FederationHttpClient(self.sydent)

    @asyncjsonwrap
    async def render_POST(self, request: Request) -> JsonDict:
        """
        Register with the Identity Server
        """
        send_cors(request)

        args = get_args(request, ("matrix_server_name", "access_token"))

        matrix_server = args["matrix_server_name"].lower()

        if not is_valid_matrix_server_name(matrix_server):
            request.setResponseCode(400)
            return {
                "errcode": "M_INVALID_PARAM",
                "error": "matrix_server_name must be a valid Matrix server name (IP address or hostname)",
            }

        def federation_request_problem(error: str) -> Dict[str, str]:
            logger.warning(error)
            request.setResponseCode(HTTPStatus.INTERNAL_SERVER_ERROR)
            return {
                "errcode": "M_UNKNOWN",
                "error": error,
            }

        try:
            result = await self.client.get_json(
                "matrix://%s/_matrix/federation/v1/openid/userinfo?access_token=%s"
                % (
                    matrix_server,
                    urllib.parse.quote(args["access_token"]),
                ),
                1024 * 5,
            )
        except (DNSLookupError, ConnectError, ResponseFailed) as e:
            return federation_request_problem(
                f"Unable to contact the Matrix homeserver ({type(e).__name__})"
            )
        except JSONDecodeError:
            return federation_request_problem(
                "The Matrix homeserver returned invalid JSON"
            )

        if "sub" not in result:
            return federation_request_problem(
                "The Matrix homeserver did not include 'sub' in its response",
            )

        user_id = result["sub"]

        if not isinstance(user_id, str):
            return federation_request_problem(
                "The Matrix homeserver returned a malformed reply"
            )

        user_id_components = user_id.split(":", 1)

        # Ensure there's a localpart and domain in the returned user ID.
        if len(user_id_components) != 2:
            return federation_request_problem(
                "The Matrix homeserver returned an invalid MXID"
            )

        user_id_server = user_id_components[1]

        if not is_valid_matrix_server_name(user_id_server):
            return federation_request_problem(
                "The Matrix homeserver returned an invalid MXID"
            )

        if user_id_server != matrix_server:
            return federation_request_problem(
                "The Matrix homeserver returned a MXID belonging to another homeserver"
            )

        tok = issueToken(self.sydent, user_id)

        # XXX: `token` is correct for the spec, but we released with `access_token`
        # for a substantial amount of time. Serve both to make spec-compliant clients
        # happy.
        return {
            "access_token": tok,
            "token": tok,
        }

    def render_OPTIONS(self, request: Request) -> bytes:
        send_cors(request)
        return b""
