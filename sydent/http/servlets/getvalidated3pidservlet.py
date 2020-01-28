# -*- coding: utf-8 -*-

# Copyright 2014 OpenMarket Ltd
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
from __future__ import absolute_import

from twisted.web.resource import Resource

from sydent.http.servlets import jsonwrap, get_args
from sydent.http.auth import authIfV2
from sydent.db.valsession import ThreePidValSessionStore
from sydent.util.stringutils import is_valid_client_secret
from sydent.validators import (
    IncorrectClientSecretException,
    InvalidSessionIdException,
    SessionExpiredException,
    SessionNotValidatedException,
)


class GetValidated3pidServlet(Resource):
    isLeaf = True

    def __init__(self, syd):
        self.sydent = syd

    @jsonwrap
    def render_GET(self, request):
        authIfV2(self.sydent, request)

        args = get_args(request, ('sid', 'client_secret'))

        sid = args['sid']
        clientSecret = args['client_secret']

        if not is_valid_client_secret(clientSecret):
            request.setResponseCode(400)
            return {
                'errcode': 'M_INVALID_PARAM',
                'error': 'Invalid client_secret provided'
            }

        valSessionStore = ThreePidValSessionStore(self.sydent)

        noMatchError = {'errcode': 'M_NO_VALID_SESSION',
                        'error': "No valid session was found matching that sid and client secret"}

        try:
            s = valSessionStore.getValidatedSession(sid, clientSecret)
        except (IncorrectClientSecretException, InvalidSessionIdException):
            request.setResponseCode(404)
            return noMatchError
        except SessionExpiredException:
            request.setResponseCode(400)
            return {'errcode': 'M_SESSION_EXPIRED',
                    'error': "This validation session has expired: call requestToken again"}
        except SessionNotValidatedException:
            request.setResponseCode(400)
            return {'errcode': 'M_SESSION_NOT_VALIDATED',
                    'error': "This validation session has not yet been completed"}

        return {'medium': s.medium, 'address': s.address, 'validated_at': s.mtime}
