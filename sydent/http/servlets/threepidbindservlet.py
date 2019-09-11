# -*- coding: utf-8 -*-

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

from twisted.web.resource import Resource

from sydent.db.valsession import ThreePidValSessionStore
from sydent.http.servlets import get_args, jsonwrap, send_cors, MatrixRestError
from sydent.http.auth import authIfV2
from sydent.validators import SessionExpiredException, IncorrectClientSecretException, InvalidSessionIdException,\
    SessionNotValidatedException

class ThreePidBindServlet(Resource):
    def __init__(self, sydent):
        self.sydent = sydent

    @jsonwrap
    def render_POST(self, request):
        send_cors(request)

        account = authIfV2(self.sydent, request)

        args = get_args(request, ('sid', 'client_secret', 'mxid'))

        sid = args['sid']
        mxid = args['mxid']
        clientSecret = args['client_secret']

        # Return the same error for not found / bad client secret otherwise people can get information about
        # sessions without knowing the secret
        noMatchError = {'errcode': 'M_NO_VALID_SESSION',
                        'error': "No valid session was found matching that sid and client secret"}

        if account:
            # This is a v2 API so only allow binding to the logged in user id
            if account.userId != mxid:
                raise MatrixRestError(403, 'M_UNAUTHORIZED', "This user is prohibited from binding to the mxid");

        try:
            valSessionStore = ThreePidValSessionStore(self.sydent)
            s = valSessionStore.getValidatedSession(sid, clientSecret)
        except IncorrectClientSecretException:
            return noMatchError
        except SessionExpiredException:
            return {'errcode': 'M_SESSION_EXPIRED',
                    'error': "This validation session has expired: call requestToken again"}
        except InvalidSessionIdException:
            return noMatchError
        except SessionNotValidatedException:
            return {'errcode': 'M_SESSION_NOT_VALIDATED',
                    'error': "This validation session has not yet been completed"}

        res = self.sydent.threepidBinder.addBinding(s.medium, s.address, mxid)
        return res

    def render_OPTIONS(self, request):
        send_cors(request)
        request.setResponseCode(200)
        return b''
