# -*- coding: utf-8 -*-

# Copyright 2018 New Vector Ltd
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


class AuthenticatedBindThreePidServlet(Resource):
    """A servlet which allows a caller to bind any 3pid they want to an mxid

    It is assumed that authentication happens out of band
    """
    def __init__(self, sydent):
        Resource.__init__(self)
        self.sydent = sydent

    @jsonwrap
    def render_POST(self, request):
        send_cors(request)
        err, args = get_args(request, ('medium', 'address', 'mxid'))
        if err:
            return err
        return self.sydent.threepidBinder.addBinding(
            args['medium'], args['address'], args['mxid'],
        )

    @jsonwrap
    def render_OPTIONS(self, request):
        send_cors(request)
        request.setResponseCode(200)
        return {}
