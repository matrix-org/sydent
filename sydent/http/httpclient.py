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
from twisted.internet import defer, reactor, ssl
from twisted.internet._sslverify import _OpenSSLECCurve, _defaultCurveName, ClientTLSOptions
from twisted.web.client import FileBodyProducer, Agent, readBody
from twisted.web.http_headers import Headers
from twisted.web.iweb import IPolicyForHTTPS
from zope.interface import implementer
from OpenSSL import SSL

logger = logging.getLogger(__name__)

class SimpleHttpClient(object):
    """
    A simple, no-frills HTTP client based on the class of the same name
    from synapse
    """
    def __init__(self, sydent, context_factory=None):
        self.sydent = sydent
        if context_factory is None:
            # The default context factory in Twisted 14.0.0 (which we require) is
            # BrowserLikePolicyForHTTPS which will do regular cert validation
            # 'like a browser'
            self.agent = Agent(
                reactor,
                connectTimeout=15,
            )
        else:
            self.agent = Agent(
                reactor,
                connectTimeout=15,
                contextFactory=context_factory
            )

    @defer.inlineCallbacks
    def get_json(self, uri):
        logger.debug("HTTP GET %s", uri)

        response = yield self.agent.request(
            "GET",
            uri.encode("ascii"),
        )
        body = yield readBody(response)
        defer.returnValue(json.loads(body))

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

@implementer(IPolicyForHTTPS)
class FederationPolicyForHTTPS(object):
    def creatorForNetloc(self, hostname, port):
        context = SSL.Context(SSL.SSLv23_METHOD)
        try:
            _ecCurve = _OpenSSLECCurve(_defaultCurveName)
            _ecCurve.addECKeyToContext(context)
        except Exception:
            logger.exception("Failed to enable elliptic curve for TLS")
        context.set_options(SSL.OP_NO_SSLv2 | SSL.OP_NO_SSLv3)

        context.set_cipher_list("!ADH:HIGH+kEDH:!AECDH:HIGH+kEECDH")
        return ClientTLSOptions(hostname, context)


class FederationHttpClient(SimpleHttpClient):
    def __init__(self, sydent):
        super(FederationHttpClient, self).__init__(sydent, FederationPolicyForHTTPS())
