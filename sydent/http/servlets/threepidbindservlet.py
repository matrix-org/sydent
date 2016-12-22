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

from twisted.web.resource import Resource

from sydent.http.servlets import get_args, jsonwrap, send_cors
from sydent.validators import SessionExpiredException, IncorrectClientSecretException, InvalidSessionIdException,\
    SessionNotValidatedException

class ThreePidBindServlet(Resource):
    def __init__(self, sydent):
        self.sydent = sydent

    @jsonwrap
    def render_POST(self, request):
        send_cors(request)
        err, args = get_args(request, ('sid', 'client_secret', 'mxid'))
        if err:
            return err

        sid = args['sid']
        mxid = args['mxid']
        clientSecret = args['client_secret']

        # Return the same error for not found / bad client secret otherwise people can get information about
        # sessions without knowing the secret
        noMatchError = {'errcode': 'M_NO_VALID_SESSION',
                        'error': "No valid session was found matching that sid and client secret"}

        try:
            res = self.sydent.threepidBinder.addBinding(sid, clientSecret, mxid)
            return res
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


    @jsonwrap
    def render_OPTIONS(self, request):
        send_cors(request)
        request.setResponseCode(200)
        return {}
