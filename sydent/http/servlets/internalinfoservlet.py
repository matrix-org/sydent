# -*- coding: utf-8 -*-

# Copyright 2019 New Vector Ltd
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

import logging
import json
import re
import copy
import yaml

from netaddr import IPAddress
from sydent.db.invite_tokens import JoinTokenStore
from sydent.http.servlets import get_args, jsonwrap, send_cors
from sydent.http.servlets.infoservlet import info_match_user_id


logger = logging.getLogger(__name__)


class InternalInfoServlet(Resource):
    isLeaf = True

    def __init__(self, syd):
        self.sydent = syd

        try:
            file = open('info.yaml')
            self.config = yaml.load(file)
            file.close()

            # medium:
            #   email:
            #     entries:
            #       matthew@matrix.org: { hs: 'matrix.org', shadow_hs: 'shadow-matrix.org' }
            #     patterns:
            #       - .*@matrix.org: { hs: 'matrix.org', shadow_hs: 'shadow-matrix.org' }

        except Exception as e:
            logger.error(e)

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
        result = info_match_user_id(medium, address)

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
