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
from typing import TYPE_CHECKING, Optional

from twisted.web.server import Request

from sydent.db.accounts import AccountStore
from sydent.http.servlets import MatrixRestError, get_args
from sydent.terms.terms import get_terms

if TYPE_CHECKING:
    from sydent.sydent import Sydent
    from sydent.users.accounts import Account

logger = logging.getLogger(__name__)


def tokenFromRequest(request: Request) -> Optional[str]:
    """Extract token from header of query parameter.

    :param request: The request to look for an access token in.

    :return: The token or None if not found
    """
    token = None
    # check for Authorization header first
    authHeader = request.getHeader("Authorization")
    if authHeader is not None and authHeader.startswith("Bearer "):
        token = authHeader[len("Bearer ") :]

    # no? try access_token query param
    if token is None:
        args = get_args(request, ("access_token",), required=False)
        token = args.get("access_token")

    return token


def authV2(
    sydent: "Sydent",
    request: Request,
    requireTermsAgreed: bool = True,
) -> "Account":
    """For v2 APIs check that the request has a valid access token associated with it

    :param sydent: The Sydent instance to use.
    :param request: The request to look for an access token in.
    :param requireTermsAgreed: Whether to deny authentication if the user hasn't accepted
        the terms of service.

    :returns Account: The account object if there is correct auth
    :raises MatrixRestError: If the request is v2 but could not be authed or the user has
        not accepted terms.
    """
    token = tokenFromRequest(request)

    if token is None:
        raise MatrixRestError(401, "M_UNAUTHORIZED", "Unauthorized")

    accountStore = AccountStore(sydent)

    account = accountStore.getAccountByToken(token)
    if account is None:
        raise MatrixRestError(401, "M_UNAUTHORIZED", "Unauthorized")

    if requireTermsAgreed:
        terms = get_terms(sydent)
        if (
            terms.getMasterVersion() is not None
            and account.consentVersion != terms.getMasterVersion()
        ):
            raise MatrixRestError(403, "M_TERMS_NOT_SIGNED", "Terms not signed")

    return account
