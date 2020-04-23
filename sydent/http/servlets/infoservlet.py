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
from netaddr import IPAddress

import logging
import json

from sydent.db.threepid_associations import GlobalAssociationStore
from sydent.http.servlets import get_args, jsonwrap, send_cors

logger = logging.getLogger(__name__)


class InfoServlet(Resource):
    """Maps a threepid to the responsible HS domain. For use by clients.

    :param syd: A sydent instance.
    :type syd: Sydent
    """

    isLeaf = True

    def __init__(self, syd):
        self.sydent = syd

    @jsonwrap
    def render_GET(self, request):
        """Clients who are "whitelisted" should receive both hs and shadow_hs in
        their response JSON. Clients that are not whitelisted should only
        receive hs, and it's contents should be that of shadow_hs in the
        config file.

        Returns: { hs: ..., [shadow_hs: ...]}
        """

        send_cors(request)
        args = get_args(request, ('medium', 'address'))

        medium = args['medium']
        address = args['address']

        # Find an entry in the info file matching this user's ID
        result = self.sydent.info.match_user_id(medium, address)

        # Check if there's a MXID associated with this address, if so use its domain as
        # the value for "hs" (so that the user can still access their account through
        # Tchap) and move the value "hs" should have had otherwise to "new_hs" if it's a
        # different one.
        store = GlobalAssociationStore(self.sydent)
        mxid = store.getMxid(medium, address)
        if mxid:
            current_hs = mxid.split(':', 1)[1]
            if current_hs != result['hs']:
                result['new_hs'] = result['hs']
                result['hs'] = current_hs

        # Non-internal. Remove 'requires_invite' if found
        result.pop('requires_invite', None)

        return result

    @jsonwrap
    def render_OPTIONS(self, request):
        send_cors(request)
        request.setResponseCode(200)
        return {}
