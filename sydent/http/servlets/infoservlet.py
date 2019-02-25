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


logger = logging.getLogger(__name__)


class InfoServlet(Resource):
    isLeaf = True

    def __init__(self, syd, internal=False):
        self.sydent = syd
        self.internal = internal

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
        Maps a threepid to the responsible HS domain, and optionally gives invitation status.
        For use by Synapse instances.
        Params: 'medium': the medium of the threepid
                'address': the address of the threepid
                'internal': whether invitation status should be returned (for access by Synapse instances)
        Returns: { hs: ..., [shadow_hs: ..., invited: true/false, requires_invite: true/false] }
        """

        send_cors(request)
        err, args = get_args(request, ('medium', 'address'))
        if err:
            return err

        medium = args['medium']
        address = args['address']

        joinTokenStore = JoinTokenStore(self.sydent)
        pendingJoinTokens = joinTokenStore.getTokens(medium, address)

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

        result = copy.deepcopy(result)

        if not self.internal:
            # Remove 'requires_invite' from responses
            result.pop('requires_invite', None)
        elif 'requires_invite' not in result:
            # If internal api and 'requires_invite' has not been specified,
            # infer False
            result['requires_invite'] = False

        if not self.internal and self.sydent.nonshadow_ips:
            # If non-internal API, determine which hs to show a client
            ip = IPAddress(self.sydent.ip_from_request(request))

            # Present shadow_hs as hs if user is from a shadow server
            if (ip not in self.sydent.nonshadow_ips):
                result['hs'] = result['shadow_hs']
                result.pop('shadow_hs', None)
            else:
                result.setdefault('shadow_hs', '')

        if self.internal:
            # Only show 'invited' if internal api
            result['invited'] = True if pendingJoinTokens else False

            # Remove `shadow_hs` if internal
            result.pop('shadow_hs', None)

        return json.dumps(result)

    @jsonwrap
    def render_OPTIONS(self, request):
        send_cors(request)
        request.setResponseCode(200)
        return {}
