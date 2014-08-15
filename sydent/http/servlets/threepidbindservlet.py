# -*- coding: utf-8 -*-

# Copyright 2014 matrix.org
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

from sydent.http.servlets import require_args, jsonwrap
from sydent.validators import SessionExpiredException, IncorrectClientSecretException, InvalidSessionIdException

class ThreePidBindServlet(Resource):
    def __init__(self, sydent):
        self.sydent = sydent

    @jsonwrap
    def render_POST(self, request):
        err = require_args(request, ('sid', 'clientSecret', 'mxId'))
        if err:
            return err

        sid = request.args['sid'][0]
        clientSecret = request.args['clientSecret'][0]
        mxId = request.args['mxId'][0]

        try:
            res = self.sydent.threepidBinder.addBinding(sid, clientSecret, mxId)
            return res
        except IncorrectClientSecretException:
            return {'error': 'incorrect-client-secret',
                    'message': "Client secret does not match the one given when requesting the token"}
        except SessionExpiredException:
            return {'error': 'session-expired',
                    'message': "This validation session has expired: call requestToken again"}
        except InvalidSessionIdException:
            return {'error': 'invalid-session-id',
                    'message': "Unknown session ID"}