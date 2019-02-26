# -*- coding: utf-8 -*-

# copyright 2019 new vector ltd
#
# licensed under the apache license, version 2.0 (the "license");
# you may not use this file except in compliance with the license.
# you may obtain a copy of the license at
#
#     http://www.apache.org/licenses/license-2.0
#
# unless required by applicable law or agreed to in writing, software
# distributed under the license is distributed on an "as is" basis,
# without warranties or conditions of any kind, either express or implied.
# see the license for the specific language governing permissions and
# limitations under the license.

from twisted.web.resource import Resource

import logging
import json

from sydent.db.invite_tokens import JoinTokenStore
from sydent.http.servlets import get_args, jsonwrap, send_cors
from sydent.http.info import Info


logger = logging.getLogger(__name__)


class InternalInfoServlet(Resource):
    isLeaf = True

    def __init__(self, syd):
        self.sydent = syd
        self.info = Info(syd)

    def render_GET(self, request):
        """
        Maps a threepid to the responsible HS domain, and gives invitation status.
        For use by Synapse instances.
        Params: 'medium': the medium of the threepid
                'address': the address of the threepid
        Returns: { hs: ..., [shadow_hs: ...], invited: true/false, requires_invite: true/false }
        """

        send_cors(request)
        err, args = get_args(request, ('medium', 'address'))
        if err:
            return err

        medium = args['medium']
        address = args['address']

        # Find an entry in the info file matching this user's ID
        result = self.info.match_user_id(medium, address)

        joinTokenStore = JoinTokenStore(self.sydent)
        pendingJoinTokens = joinTokenStore.getTokens(medium, address)

        # Report whether this user has been invited to a room
        result['invited'] = True if pendingJoinTokens else False
        return json.dumps(result)

    @jsonwrap
    def render_OPTIONS(self, request):
        send_cors(request)
        request.setResponseCode(200)
        return {}
