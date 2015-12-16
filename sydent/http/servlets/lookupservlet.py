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
from sydent.db.threepid_associations import GlobalAssociationStore

import json

from sydent.http.servlets import require_args, jsonwrap, send_cors
import syutil.crypto.jsonsign


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

        sgassoc = json.loads(sgassoc.encode('utf8'))
        if not self.sydent.server_name in sgassoc['signatures']:
            # We have not yet worked out what the proper trust model should be.
            #
            # Maybe clients implicitly trust a server they talk to (and so we
            # should sign every assoc we return as ourselves, so they can
            # verify this).
            #
            # Maybe clients really want to know what server did the original
            # verification, and want to only know exactly who signed the assoc.
            #
            # Until we work out what we should do, sign all assocs we return as
            # ourself. This is vaguely ok because there actually is only one
            # identity server, but it happens to have two names (matrix.org and
            # vector.im), and so we're not really lying too much.
            #
            # We do this when we return assocs, not when we receive them over
            # replication, so that we can undo this decision in the future if
            # we wish, without having destroyed the raw underlying data.
            sgassoc = syutil.crypto.jsonsign.sign_json(
                sgassoc,
                self.sydent.server_name,
                self.sydent.keyring.ed25519
            )
        return json.dumps(sgassoc)

    @jsonwrap
    def render_OPTIONS(self, request):
        send_cors(request)
        request.setResponseCode(200)
        return {}