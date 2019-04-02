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

from sydent.http.servlets import get_args, jsonwrap, send_cors

logger = logging.getLogger(__name__)


class InfoServlet(Resource):
    """Maps a threepid to the responsible HS domain. For use by clients.

    :param syd: A sydent instance.
    :type syd: Sydent
    :param info: An instance of Info.
    :type info: Sydent.http.Info
    """

    isLeaf = True

    def __init__(self, syd, info):
        self.sydent = syd
        self.info = info

    def render_GET(self, request):
        """Clients who are "whitelisted" should receive both hs and shadow_hs in
        their response JSON. Clients that are not whitelisted should only
        receive hs, and it's contents should be that of shadow_hs in the
        config file.

        Returns: { hs: ..., [shadow_hs: ...]}
        """

        send_cors(request)
        err, args = get_args(request, ('medium', 'address'))
        if err:
            return err

        medium = args['medium']
        address = args['address']

        # Find an entry in the info file matching this user's ID
        result = self.info.match_user_id(medium, address)

        # Check if this user is from a shadow hs/not whitelisted
        ip = IPAddress(self.sydent.ip_from_request(request))
        if self.sydent.nonshadow_ips and ip not in self.sydent.nonshadow_ips:
            # This user is not whitelisted, present shadow_hs at their only hs
            result['hs'] = result.pop('shadow_hs', None)

        # Non-internal. Remove 'requires_invite' if found
        result.pop('requires_invite', None)

        return json.dumps(result)

    @jsonwrap
    def render_OPTIONS(self, request):
        send_cors(request)
        request.setResponseCode(200)
        return {}
