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

from sydent.threepid.assocsigner import AssociationSigner
from sydent.http.servlets import jsonwrap, require_args

class LookupServlet(Resource):
    isLeaf = True

    def __init__(self, syd):
        self.sydent = syd

    @jsonwrap
    def render_GET(self, request):
        err = require_args(request, ('medium', 'address'))
        if err:
            return err

        medium = request.args['medium'][0]
        address = request.args['address'][0]

        globalAssocStore = GlobalAssociationStore(self.sydent)

        assoc = globalAssocStore.associationForThreepid(medium, address)

        if not assoc:
            return json.dumps({})

        mxid = row[0]
        created = row[1]
        expires = row[2]

        assocSigner = AssociationSigner(self.sydent)

        dfljgdlfgj

        sgassoc = assocSigner.signedThreePidAssociation(medium, address, mxid, created, expires)
        return json.dumps(sgassoc)
