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
from twisted.web.client import FileBodyProducer, Agent, readBody
from twisted.web.http_headers import Headers
from sydent.http.matrixfederationagent import MatrixFederationAgent

from sydent.http.federation_tls_options import ClientTLSOptionsFactory

logger = logging.getLogger(__name__)

class HTTPClient(object):
    """A base HTTP class that contains methods for making GET and POST HTTP
    requests.
    """
    @defer.inlineCallbacks
    def get_json(self, uri):
        """Make a GET request to an endpoint returning JSON and parse result

        :param uri: The URI to make a GET request to.
        :type uri: str
        :returns a deferred containing JSON parsed into a Python object.
        :rtype: Deferred[any]
        """
        logger.debug("HTTP GET %s", uri)

        response = yield self.agent.request(
            "GET",
            uri.encode("ascii"),
        )
        body = yield readBody(response)
        try:
            json_body = json.loads(body)
        except Exception as e:
            logger.exception("Error parsing JSON from %s", uri)
            raise
        defer.returnValue(json_body)

    @defer.inlineCallbacks
    def post_json_get_nothing(self, uri, post_json, opts):
        """Make a GET request to an endpoint returning JSON and parse result

        :param uri: The URI to make a GET request to.
        :type uri: str

        :param post_json: A Python object that will be converted to a JSON
            string and POSTed to the given URI.
        :type post_json: any

        :opts: A dictionary of request options. Currently only opts.headers
            is supported.
        :type opts: Dict[str,any]

        :returns a response from the remote server.
        :rtype: Deferred[twisted.web.iweb.IResponse]
        """
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

        # Ensure the body object is read otherwise we'll leak HTTP connections
        # as per
        # https://twistedmatrix.com/documents/current/web/howto/client.html
        yield readBody(response)

        defer.returnValue(response)

class SimpleHttpClient(HTTPClient):
    """A simple, no-frills HTTP client based on the class of the same name
    from Synapse.
    """
    def __init__(self, sydent):
        self.sydent = sydent
        # The default endpoint factory in Twisted 14.0.0 (which we require) uses the
        # BrowserLikePolicyForHTTPS context factory which will do regular cert validation
        # 'like a browser'
        self.agent = Agent(
            reactor,
            connectTimeout=15,
        )

class FederationHttpClient(HTTPClient):
    """HTTP client for federation requests to homeservers. Uses a
    MatrixFederationAgent.
    """
    def __init__(self, sydent):
        self.sydent = sydent
        self.agent = MatrixFederationAgent(
            reactor,
            ClientTLSOptionsFactory(sydent.cfg),
        )
