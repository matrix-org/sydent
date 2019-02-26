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

import logging
import json
import re
import copy
import yaml

from netaddr import IPAddress
from sydent.db.invite_tokens import JoinTokenStore
from sydent.http.servlets import get_args, jsonwrap, send_cors


logger = logging.getLogger(__name__)


class InfoServlet(Resource):
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

    def info_match_user_id(medium, address):
        """Return information for a given medium/address combination.

        :param medium: The medium of the address.
        :type medium: str
        :param address: The address of the 3PID.
        :type address: str
        :returns a dict
        """
        result = {}

        # Find an entry in the info file matching this user's ID
        if address in self.config['medium']['email']['entries']:
            result = self.config['medium']['email']['entries'][address]
        else:
            for pattern_group in self.config['medium']['email']['patterns']:
                for pattern in pattern_group:
                    if (re.match("^" + pattern + "$", address)):
                        result = pattern_group[pattern]
                        break
                if result:
                    break

        # Change output if user is from a shadow homeserver
        if self.sydent.nonshadow_ips:
            ip = IPAddress(self.sydent.ip_from_request(request))

            # Present shadow_hs as hs if user is from a shadow server
            if (ip not in self.sydent.nonshadow_ips):
                result['hs'] = result['shadow_hs']
                result.pop('shadow_hs', None)
            else:
                result.setdefault('shadow_hs', '')

        return result

    def render_GET(self, request):
        """
        Maps a threepid to the responsible HS domain. For use by clients.
        Params: 'medium': the medium of the threepid
                'address': the address of the threepid
        Returns: { hs: ..., [shadow_hs: ...]}
        """

        send_cors(request)
        err, args = get_args(request, ('medium', 'address'))
        if err:
            return err

        medium = args['medium']
        address = args['address']

        # Find an entry in the info file matching this user's ID
        result = info_match_user_id(medium, address)

        # Non-internal. Remove 'requires_invite' if found
        result.pop('requires_invite', None)

        return json.dumps(result)

    @jsonwrap
    def render_OPTIONS(self, request):
        send_cors(request)
        request.setResponseCode(200)
        return {}
