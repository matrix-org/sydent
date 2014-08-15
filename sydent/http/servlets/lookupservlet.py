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

import json

from sydent.util import validationutils

class LookupServlet(Resource):
    isLeaf = True

    def __init__(self, syd):
        self.sydent = syd

    def render_GET(self, request):
        if not 'medium' in request.args or not 'address' in request.args:
            request.setResponseCode(400)
            resp = {'error': 'badrequest', 'message': "'medium' and 'address' fields are required"}
            return json.dumps(resp)

        medium = request.args['medium'][0]
        address = request.args['address'][0]

        cur = self.sydent.db.cursor()

        # sqlite's support for upserts is atrocious but this is temporary anyway
        res = cur.execute("select mxid,createdAt,expires from threepid_associations "+
                    "where medium = ? and address = ?", (medium, address))
        row = res.fetchone()
        if not row:
            return json.dumps({})

        mxid = row[0]
        created = row[1]
        expires = row[2]

        sgassoc = validationutils.signedThreePidAssociation(self.sydent, medium, address, mxid, created, expires)
        return json.dumps(sgassoc)
