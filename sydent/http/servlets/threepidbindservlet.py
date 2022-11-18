# Copyright 2014 OpenMarket Ltd
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

from sydent.db.valsession import ThreePidValSessionStore
from sydent.http.auth import authV2
from sydent.http.servlets import (
    MatrixRestError,
    SydentResource,
    get_args,
    jsonwrap,
    send_cors,
)
from sydent.types import JsonDict
from sydent.util.stringutils import is_valid_client_secret
from sydent.validators import (
    IncorrectClientSecretException,
    InvalidSessionIdException,
    SessionExpiredException,
    SessionNotValidatedException,
)

if TYPE_CHECKING:
    from sydent.sydent import Sydent


class ThreePidBindServlet(SydentResource):
    def __init__(self, sydent: "Sydent", require_auth: bool = False) -> None:
        super().__init__()
        self.sydent = sydent
        self.require_auth = require_auth

    @jsonwrap
    def render_POST(self, request: Request) -> JsonDict:
        send_cors(request)

        account = None
        if self.require_auth:
            account = authV2(self.sydent, request)

        args = get_args(request, ("sid", "client_secret", "mxid"))

        sid = args["sid"]
        mxid = args["mxid"]
        clientSecret = args["client_secret"]

        if not is_valid_client_secret(clientSecret):
            raise MatrixRestError(
                400, "M_INVALID_PARAM", "Invalid client_secret provided"
            )

        if account:
            # This is a v2 API so only allow binding to the logged in user id
            if account.userId != mxid:
                raise MatrixRestError(
                    403,
                    "M_UNAUTHORIZED",
                    "This user is prohibited from binding to the mxid",
                )

        try:
            valSessionStore = ThreePidValSessionStore(self.sydent)
            s = valSessionStore.getValidatedSession(sid, clientSecret)
        except (IncorrectClientSecretException, InvalidSessionIdException):
            # Return the same error for not found / bad client secret otherwise
            # people can get information about sessions without knowing the
            # secret.
            raise MatrixRestError(
                404,
                "M_NO_VALID_SESSION",
                "No valid session was found matching that sid and client secret",
            )
        except SessionExpiredException:
            raise MatrixRestError(
                400,
                "M_SESSION_EXPIRED",
                "This validation session has expired: call requestToken again",
            )
        except SessionNotValidatedException:
            raise MatrixRestError(
                400,
                "M_SESSION_NOT_VALIDATED",
                "This validation session has not yet been completed",
            )

        res = self.sydent.threepidBinder.addBinding(s.medium, s.address, mxid)
        return res

    def render_OPTIONS(self, request: Request) -> bytes:
        send_cors(request)
        return b""
