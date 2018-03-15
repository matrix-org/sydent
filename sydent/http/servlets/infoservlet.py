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
            close(file)

            # medium:
            #   email:
            #     entries:
            #       matthew@matrix.org: { hs: 'matrix.org' }
            #     patterns:
            #       - .*@matrix.org: { hs: 'matrix.org' }

        except Exception as e:
            logger.error(e)

    def render_GET(self, request):
        """
        Maps a threepid to the responsible HS domain, and gives invitation status
        Params: 'medium': the medium of the threepid
                'address': the address of the threepid
        Returns: { hs: ..., invited: true/false }
        """

        # TODO: lock this so it can only be called by the HS?

        send_cors(request)
        err, args = get_args(request, ('medium', 'address'))
        if err:
            return err

        medium = args['medium']
        address = args['address']

        joinTokenStore = JoinTokenStore(self.sydent)
        pendingJoinTokens = joinTokenStore.getTokens(medium, address)

        result = {}

        if address in self.config['medium']['email']['entries']:
            result = self.config['medium']['email']['entries'][address]
        else:
            for pattern in self.config['medium']['email']['patterns']:
                if (re.match("^" + pattern + "$", address)):
                    result = self.config['medium']['email']['patterns'][pattern]

        result = copy.deepcopy(result)
        result['invited'] = True if pendingJoinTokens else False
        return json.dumps(result)

    @jsonwrap
    def render_OPTIONS(self, request):
        send_cors(request)
        request.setResponseCode(200)
        return {}
