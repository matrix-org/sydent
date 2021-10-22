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
import logging
from typing import Callable

from OpenSSL import SSL
from twisted.internet import ssl
from twisted.internet.abstract import isIPAddress, isIPv6Address
from twisted.internet.interfaces import IOpenSSLClientConnectionCreator
from twisted.protocols.tls import TLSMemoryBIOProtocol
from twisted.python.failure import Failure
from zope.interface import implementer

logger = logging.getLogger(__name__)

F = Callable[[SSL.Connection, int, int], None]


def _tolerateErrors(wrapped: F) -> F:
    """
    Wrap up an info_callback for pyOpenSSL so that if something goes wrong
    the error is immediately logged and the connection is dropped if possible.
    This is a copy of twisted.internet._sslverify._tolerateErrors. For
    documentation, see the twisted documentation.
    """

    def infoCallback(connection: SSL.Connection, where: int, ret: int) -> None:
        try:
            return wrapped(connection, where, ret)
        except BaseException:
            f = Failure()
            logger.exception("Error during info_callback")
            connection.get_app_data().failVerification(f)

    return infoCallback


def _idnaBytes(text: str) -> bytes:
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
class ClientTLSOptions:
    """
    Client creator for TLS without certificate identity verification. This is a
    copy of twisted.internet._sslverify.ClientTLSOptions with the identity
    verification left out. For documentation, see the twisted documentation.
    """

    def __init__(self, hostname: str, ctx: SSL.Context):
        self._ctx = ctx

        if isIPAddress(hostname) or isIPv6Address(hostname):
            self._hostnameBytes = hostname.encode("ascii")
            self._sendSNI = False
        else:
            self._hostnameBytes = _idnaBytes(hostname)
            self._sendSNI = True

        ctx.set_info_callback(_tolerateErrors(self._identityVerifyingInfoCallback))

    def clientConnectionForTLS(
        self, tlsProtocol: TLSMemoryBIOProtocol
    ) -> SSL.Connection:
        context = self._ctx
        connection = SSL.Connection(context, None)
        connection.set_app_data(tlsProtocol)
        return connection

    def _identityVerifyingInfoCallback(
        self, connection: SSL.Connection, where: int, ret: int
    ) -> None:
        # Literal IPv4 and IPv6 addresses are not permitted
        # as host names according to the RFCs
        if where & SSL.SSL_CB_HANDSHAKE_START and self._sendSNI:
            connection.set_tlsext_host_name(self._hostnameBytes)


class ClientTLSOptionsFactory:
    """Factory for Twisted ClientTLSOptions that are used to make connections
    to remote servers for federation."""

    def __init__(self, verify_requests: bool):
        if verify_requests:
            self._options = ssl.CertificateOptions(trustRoot=ssl.platformTrust())
        else:
            self._options = ssl.CertificateOptions()

    def get_options(self, host: str) -> ClientTLSOptions:
        # Use _makeContext so that we get a fresh OpenSSL CTX each time.
        return ClientTLSOptions(host, self._options._makeContext())
