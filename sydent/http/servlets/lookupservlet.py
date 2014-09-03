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
from sydent.db.threepid_associations import GlobalAssociationStore

import json

from sydent.http.servlets import require_args, jsonwrap, send_cors

class LookupServlet(Resource):
    isLeaf = True

    def __init__(self, syd):
        self.sydent = syd

    def render_GET(self, request):
        send_cors(request)
        err = require_args(request, ('medium', 'address'))
        if err:
            return err

        medium = request.args['medium'][0]
        address = request.args['address'][0]

        globalAssocStore = GlobalAssociationStore(self.sydent)

        sgassoc = globalAssocStore.signedAssociationStringForThreepid(medium, address)

        if not sgassoc:
            return json.dumps({})

        return sgassoc.encode('utf8')

    @jsonwrap
    def render_OPTIONS(self, request):
        send_cors(request)
        request.setResponseCode(200)
        return {}