# -*- coding: utf-8 -*-

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

import twisted.internet.ssl

from sydent.db.accounts import AccountStore
from sydent.terms.terms import get_terms
from sydent.http.servlets import MatrixRestError


logger = logging.getLogger(__name__)

def tokenFromRequest(request):
    """Extract token from header of query parameter.

    :returns str|None: The token or None if not found
    """
    token = None
    # check for Authorization header first
    authHeader = request.getHeader('Authorization')
    if authHeader is not None and authHeader.startswith('Bearer '):
        token = authHeader[len("Bearer "):]

    # no? try access_token query param
    if token is None and 'access_token' in request.args:
        token = request.args['access_token'][0]

    return token

def authIfV2(sydent, request, requireTermsAgreed=True):
    """For v2 APIs check that the request has a valid access token associated with it

    :returns Account|None: The account object if there is correct auth, or None for v1 APIs
    :raises MatrixRestError: If the request is v2 but could not be authed or the user has not accepted terms
    """
    if request.path.startswith('/_matrix/identity/v2'):
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
                terms.getMasterVersion() is not None and
                account.consentVersion != terms.getMasterVersion()
            ):
                raise MatrixRestError(403, "M_TERMS_NOT_SIGNED", "Terms not signed")

        return account
    return None
