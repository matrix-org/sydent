# -*- coding: utf-8 -*-

# Copyright 2016 OpenMarket Ltd
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

import json
import logging

from StringIO import StringIO
from twisted.internet import defer, reactor
from twisted.web.client import FileBodyProducer, Agent
from twisted.web.http_headers import Headers

logger = logging.getLogger(__name__)

class SimpleHttpClient(object):
    """
    A simple, no-frills HTTP client based on the class of the same name
    from synapse
    """
    def __init__(self, sydent):
        self.sydent = sydent
        # The default context factory in Twisted 14.0.0 (which we require) is
        # BrowserLikePolicyForHTTPS which will do regular cert validation
        # 'like a browser'
        self.agent = Agent(
            reactor,
            connectTimeout=15,
        )

    @defer.inlineCallbacks
    def post_json_get_nothing(self, uri, post_json, opts):
        json_str = json.dumps(post_json)

        headers = opts.get('headers', Headers({
            b"Content-Type": [b"application/json"],
        }))

        logger.debug("HTTP POST %s -> %s", json_str, uri)

        response = yield self.agent.request(
            "POST",
            uri.encode("ascii"),
            headers,
            bodyProducer=FileBodyProducer(StringIO(json_str))
        )
        defer.returnValue(response)

