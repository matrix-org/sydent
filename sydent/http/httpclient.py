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

from zope.interface import implementer
from StringIO import StringIO
from twisted.internet import defer, reactor, ssl
from twisted.internet.interfaces import IOpenSSLClientConnectionCreator
from twisted.internet.abstract import isIPAddress, isIPv6Address
from twisted.internet.endpoints import HostnameEndpoint, wrapClientTLS
from twisted.internet._sslverify import _defaultCurveName, ClientTLSOptions
from twisted.web.client import FileBodyProducer, Agent, readBody
from twisted.web.http_headers import Headers
import twisted.names.client
from twisted.names.error import DNSNameError
from OpenSSL import SSL, crypto
from matrixfederationagent import MatrixFederationAgent

logger = logging.getLogger(__name__)

class HTTPClient(object):
    @defer.inlineCallbacks
    def get_json(self, uri):
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
            json_body = None
        defer.returnValue(json_body)

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

class SimpleHttpClient(HTTPClient):
    """
    A simple, no-frills HTTP client based on the class of the same name
    from Synapse.
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

class FederationHttpClient(HTTPClient):
    def __init__(self, sydent):
        self.sydent = sydent
        self.agent = MatrixFederationAgent(
            reactor,
            ClientTLSOptionsFactory(),
        )

def _tolerateErrors(wrapped):
    """
    Wrap up an info_callback for pyOpenSSL so that if something goes wrong
    the error is immediately logged and the connection is dropped if possible.
    This is a copy of twisted.internet._sslverify._tolerateErrors. For
    documentation, see the twisted documentation.
    """

    def infoCallback(connection, where, ret):
        try:
            return wrapped(connection, where, ret)
        except:  # noqa: E722, taken from the twisted implementation
            f = Failure()
            logger.exception("Error during info_callback")
            connection.get_app_data().failVerification(f)

    return infoCallback

def _idnaBytes(text):
    """
    Convert some text typed by a human into some ASCII bytes. This is a
    copy of twisted.internet._idna._idnaBytes. For documentation, see the
    twisted documentation.
    """
    try:
        import idna
    except ImportError:
        return text.encode("idna")
    else:
        return idna.encode(text)

@implementer(IOpenSSLClientConnectionCreator)
class ClientTLSOptions(object):
    """
    Client creator for TLS without certificate identity verification. This is a
    copy of twisted.internet._sslverify.ClientTLSOptions with the identity
    verification left out. For documentation, see the twisted documentation.
    """

    def __init__(self, hostname, ctx):
        self._ctx = ctx

        if isIPAddress(hostname) or isIPv6Address(hostname):
            self._hostnameBytes = hostname.encode('ascii')
            self._sendSNI = False
        else:
            self._hostnameBytes = _idnaBytes(hostname)
            self._sendSNI = True

        ctx.set_info_callback(_tolerateErrors(self._identityVerifyingInfoCallback))

    def clientConnectionForTLS(self, tlsProtocol):
        context = self._ctx
        connection = SSL.Connection(context, None)
        connection.set_app_data(tlsProtocol)
        return connection

    def _identityVerifyingInfoCallback(self, connection, where, ret):
        # Literal IPv4 and IPv6 addresses are not permitted
        # as host names according to the RFCs
        if where & SSL.SSL_CB_HANDSHAKE_START and self._sendSNI:
            connection.set_tlsext_host_name(self._hostnameBytes)


class ClientTLSOptionsFactory(object):
    """Factory for Twisted ClientTLSOptions that are used to make connections
    to remote servers for federation."""

    def __init__(self):
        # We don't use config options yet
        self._options = ssl.CertificateOptions(verify=False)

    def get_options(self, host):
        # Use _makeContext so that we get a fresh OpenSSL CTX each time.
        return ClientTLSOptions(host, self._options._makeContext())