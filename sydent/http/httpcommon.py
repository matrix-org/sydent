# Copyright 2014 OpenMarket Ltd
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
from io import BytesIO
from typing import TYPE_CHECKING, Optional, cast

import twisted.internet.ssl
from twisted.internet import defer, protocol
from twisted.internet._sslverify import IOpenSSLTrustRoot
from twisted.internet.interfaces import ITCPTransport
from twisted.internet.protocol import connectionDone
from twisted.python.failure import Failure
from twisted.web import server
from twisted.web.client import ResponseDone
from twisted.web.http import PotentialDataLoss
from twisted.web.iweb import UNKNOWN_LENGTH, IResponse

if TYPE_CHECKING:
    from sydent.sydent import Sydent


logger = logging.getLogger(__name__)

# Arbitrarily limited to 512 KiB.
MAX_REQUEST_SIZE = 512 * 1024


class SslComponents:
    def __init__(self, sydent: "Sydent") -> None:
        self.sydent = sydent

        self.myPrivateCertificate = self.makeMyCertificate()
        self.trustRoot = self.makeTrustRoot()

    def makeMyCertificate(self) -> Optional[twisted.internet.ssl.PrivateCertificate]:
        # TODO Move some of this loading into parse_config
        privKeyAndCertFilename = self.sydent.config.http.cert_file

        if privKeyAndCertFilename == "":
            logger.warning(
                "No HTTPS private key / cert found: not starting replication server "
                "or doing replication pushes"
            )
            return None

        try:
            fp = open(privKeyAndCertFilename)
        except OSError:
            logger.warning(
                "Unable to read private key / cert file from %s: not starting the replication HTTPS server "
                "or doing replication pushes.",
                privKeyAndCertFilename,
            )
            return None

        authData = fp.read()
        fp.close()
        return twisted.internet.ssl.PrivateCertificate.loadPEM(authData)

    def makeTrustRoot(self) -> IOpenSSLTrustRoot:
        # If this option is specified, use a specific root CA cert. This is useful for testing when it's not
        # practical to get the client cert signed by a real root CA but should never be used on a production server.
        caCertFilename = self.sydent.config.http.ca_cert_file
        if len(caCertFilename) > 0:
            try:
                fp = open(caCertFilename)
                caCert = twisted.internet.ssl.Certificate.loadPEM(fp.read())
                fp.close()
            except Exception:
                logger.warning("Failed to open CA cert file %s", caCertFilename)
                raise
            logger.warning("Using custom CA cert file: %s", caCertFilename)
            # Type ignore: I'm not going to add a stub for the semiprivate
            # _sslverify module. I've already taken on too much stubbing as it is!
            return twisted.internet._sslverify.OpenSSLCertificateAuthorities(  # type: ignore
                [caCert.original]
            )
        else:
            return twisted.internet.ssl.OpenSSLDefaultPaths()


class BodyExceededMaxSize(Exception):
    """The maximum allowed size of the HTTP body was exceeded."""


class _DiscardBodyWithMaxSizeProtocol(protocol.Protocol):
    """A protocol which immediately errors upon receiving data."""

    transport: ITCPTransport

    def __init__(self, deferred: "defer.Deferred[bytes]") -> None:
        self.deferred = deferred

    def _maybe_fail(self) -> None:
        """
        Report a max size exceed error and disconnect the first time this is called.
        """
        if not self.deferred.called:
            self.deferred.errback(BodyExceededMaxSize())
            # Close the connection (forcefully) since all the data will get
            # discarded anyway.
            self.transport.abortConnection()

    def dataReceived(self, data: bytes) -> None:
        self._maybe_fail()

    def connectionLost(self, reason: Failure = connectionDone) -> None:
        self._maybe_fail()


class _ReadBodyWithMaxSizeProtocol(protocol.Protocol):
    """A protocol which reads body to a stream, erroring if the body exceeds a maximum size."""

    transport: ITCPTransport

    def __init__(
        self, deferred: "defer.Deferred[bytes]", max_size: Optional[int]
    ) -> None:
        self.stream = BytesIO()
        self.deferred = deferred
        self.length = 0
        self.max_size = max_size

    def dataReceived(self, data: bytes) -> None:
        # If the deferred was called, bail early.
        if self.deferred.called:
            return

        self.stream.write(data)
        self.length += len(data)
        # The first time the maximum size is exceeded, error and cancel the
        # connection. dataReceived might be called again if data was received
        # in the meantime.
        if self.max_size is not None and self.length >= self.max_size:
            self.deferred.errback(BodyExceededMaxSize())
            # Close the connection (forcefully) since all the data will get
            # discarded anyway.
            if self.transport is not None:
                self.transport.abortConnection()

    def connectionLost(self, reason: Failure = connectionDone) -> None:
        # If the maximum size was already exceeded, there's nothing to do.
        if self.deferred.called:
            return

        if reason.check(ResponseDone):
            self.deferred.callback(self.stream.getvalue())
        elif reason.check(PotentialDataLoss):
            # stolen from https://github.com/twisted/treq/pull/49/files
            # http://twistedmatrix.com/trac/ticket/4840
            self.deferred.callback(self.stream.getvalue())
        else:
            self.deferred.errback(reason)


def read_body_with_max_size(
    response: IResponse, max_size: Optional[int]
) -> "defer.Deferred[bytes]":
    """
    Read a HTTP response body to a file-object. Optionally enforcing a maximum file size.

    If the maximum file size is reached, the returned Deferred will resolve to a
    Failure with a BodyExceededMaxSize exception.

    Args:
        response: The HTTP response to read from.
        max_size: The maximum file size to allow.

    Returns:
        A Deferred which resolves to the read body.
    """
    d: "defer.Deferred[bytes]" = defer.Deferred()

    # If the Content-Length header gives a size larger than the maximum allowed
    # size, do not bother downloading the body.
    # Type safety: twisted guarantees that response.length is either the
    # "opaque" object UNKNOWN_LENGTH, or else an int.
    if max_size is not None and response.length != UNKNOWN_LENGTH:
        response.length = cast(int, response.length)
        if response.length > max_size:
            response.deliverBody(_DiscardBodyWithMaxSizeProtocol(d))
            return d

    response.deliverBody(_ReadBodyWithMaxSizeProtocol(d, max_size))
    return d


class SizeLimitingRequest(server.Request):
    def handleContentChunk(self, data: bytes) -> None:
        if self.content.tell() + len(data) > MAX_REQUEST_SIZE:
            logger.info(
                "Aborting connection from %s because the request exceeds maximum size",
                # Formerly `self.client.host`, but `host` isn't provided by `IAddress`
                self.client,
            )
            assert self.transport is not None
            self.transport.abortConnection()
            return

        return super().handleContentChunk(data)
