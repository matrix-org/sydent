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
from twisted.internet.endpoints import HostnameEndpoint, wrapClientTLS
from twisted.internet._sslverify import _defaultCurveName, ClientTLSOptions
from twisted.web.client import FileBodyProducer, Agent, readBody
from twisted.web.http_headers import Headers
import twisted.names.client
from twisted.names.error import DNSNameError
from OpenSSL import SSL, crypto

logger = logging.getLogger(__name__)


class SimpleHttpClient(object):
    """
    A simple, no-frills HTTP client based on the class of the same name
    from synapse
    """
    def __init__(self, sydent, endpoint_factory=None):
        self.sydent = sydent
        if endpoint_factory is None:
            # The default endpoint factory in Twisted 14.0.0 (which we require) uses the
            # BrowserLikePolicyForHTTPS context factory which will do regular cert validation
            # 'like a browser'
            self.agent = Agent(
                reactor,
                connectTimeout=15,
            )
        else:
            self.agent = Agent.usingEndpointFactory(
                reactor,
                endpoint_factory,
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

class SRVClientEndpoint(object):
    def __init__(self, reactor, service, domain, protocol="tcp",
                 default_port=None, endpoint=HostnameEndpoint,
                 endpoint_kw_args={}):
        self.reactor = reactor
        self.domain = domain

        self.endpoint = endpoint
        self.endpoint_kw_args = endpoint_kw_args

    @defer.inlineCallbacks
    def lookup_server(self):
        service_name = "%s.%s.%s" % ('_matrix', '_tcp', self.domain)

        default = self.domain, 8448

        try:
            answers, _, _ = yield twisted.names.client.lookupService(service_name)
        except DNSNameError:
            logger.info("DNSNameError doing SRV lookup for %s - using default", service_name)
            defer.returnValue(default)

        for answer in answers:
            if answer.type != twisted.names.dns.SRV or not answer.payload:
                continue

            # XXX we just use the first
            logger.info("Got SRV answer: %r / %d for %s", str(answer.payload.target), answer.payload.port, service_name)
            defer.returnValue((str(answer.payload.target), answer.payload.port))

        logger.info("No valid answers found in response from %s (%r)", self.domain, answers)
        defer.returnValue(default)

    @defer.inlineCallbacks
    def connect(self, protocolFactory):
        server = yield self.lookup_server()
        logger.info("Connecting to %s:%s", server[0], server[1])
        endpoint = self.endpoint(
            self.reactor, server[0], server[1], **self.endpoint_kw_args
        )
        connection = yield endpoint.connect(protocolFactory)
        defer.returnValue(connection)

def matrix_federation_endpoint(reactor, destination, ssl_context_factory=None,
                               timeout=None):
    """Construct an endpoint for the given matrix destination.

    :param reactor: Twisted reactor.
    :param destination: The name of the server to connect to.
    :type destination: bytes
    :param ssl_context_factory: Factory which generates SSL contexts to use for TLS.
    :type ssl_context_factory: twisted.internet.ssl.ContextFactory
    :param timeout (int): connection timeout in seconds
    :type timeout: int
    """

    domain_port = destination.split(":")
    domain = domain_port[0]
    port = int(domain_port[1]) if domain_port[1:] else None

    endpoint_kw_args = {}

    if timeout is not None:
        endpoint_kw_args.update(timeout=timeout)

    if ssl_context_factory is None:
        transport_endpoint = HostnameEndpoint
        default_port = 8008
    else:
        def transport_endpoint(reactor, host, port, timeout):
            return wrapClientTLS(
                ssl_context_factory,
                HostnameEndpoint(reactor, host, port, timeout=timeout))
        default_port = 8448

    if port is None:
        return SRVClientEndpoint(
            reactor, "matrix", domain, protocol="tcp",
            default_port=default_port, endpoint=transport_endpoint,
            endpoint_kw_args=endpoint_kw_args
        )
    else:
        return transport_endpoint(
            reactor, domain, port, **endpoint_kw_args
        )

class FederationEndpointFactory(object):
    def endpointForURI(self, uri):
        destination = uri.netloc
        context_factory = FederationContextFactory()

        return matrix_federation_endpoint(
            reactor, destination, timeout=10,
            ssl_context_factory=context_factory,
        )

class FederationContextFactory(object):
    def getContext(self):
        context = SSL.Context(SSL.SSLv23_METHOD)
        try:
            _ecCurve = crypto.get_elliptic_curve(_defaultCurveName)
            context.set_tmp_ecdh(_ecCurve)
        except Exception:
            logger.exception("Failed to enable elliptic curve for TLS")
        context.set_options(SSL.OP_NO_SSLv2 | SSL.OP_NO_SSLv3)

        context.set_cipher_list("!ADH:HIGH+kEDH:!AECDH:HIGH+kEECDH")
        return context

class FederationHttpClient(SimpleHttpClient):
    def __init__(self, sydent):
        super(FederationHttpClient, self).__init__(sydent, FederationEndpointFactory())
