# -*- coding: utf-8 -*-

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

import twisted.internet.ssl
from twisted.internet import defer, protocol
from twisted.internet.protocol import connectionDone
from twisted.web._newclient import ResponseDone
from twisted.web.http import PotentialDataLoss
from twisted.web.iweb import UNKNOWN_LENGTH

logger = logging.getLogger(__name__)

class SslComponents:
    def __init__(self, sydent):
        self.sydent = sydent

        self.myPrivateCertificate = self.makeMyCertificate()
        self.trustRoot = self.makeTrustRoot()

    def makeMyCertificate(self):
        privKeyAndCertFilename = self.sydent.cfg.get('http', 'replication.https.certfile')
        if privKeyAndCertFilename == '':
            logger.warn("No HTTPS private key / cert found: not starting replication server "
                        "or doing replication pushes")
            return None

        try:
            fp = open(privKeyAndCertFilename)
        except IOError:
            logger.warn("Unable to read private key / cert file from %s: not starting the replication HTTPS server "
                        "or doing replication pushes.",
                        privKeyAndCertFilename)
            return None

        authData = fp.read()
        fp.close()
        return twisted.internet.ssl.PrivateCertificate.loadPEM(authData)

    def makeTrustRoot(self):
        # If this option is specified, use a specific root CA cert. This is useful for testing when it's not
        # practical to get the client cert signed by a real root CA but should never be used on a production server.
        caCertFilename = self.sydent.cfg.get('http', 'replication.https.cacert')
        if len(caCertFilename) > 0:
            try:
                fp = open(caCertFilename)
                caCert = twisted.internet.ssl.Certificate.loadPEM(fp.read())
                fp.close()
            except:
                logger.warn("Failed to open CA cert file %s", caCertFilename)
                raise
            logger.warn("Using custom CA cert file: %s", caCertFilename)
            return twisted.internet._sslverify.OpenSSLCertificateAuthorities([caCert.original])
        else:
            return twisted.internet.ssl.OpenSSLDefaultPaths()



class BodyExceededMaxSize(Exception):
    """The maximum allowed size of the HTTP body was exceeded."""


class _DiscardBodyWithMaxSizeProtocol(protocol.Protocol):
    """A protocol which immediately errors upon receiving data."""

    def __init__(self, deferred):
        self.deferred = deferred

    def _maybe_fail(self):
        """
        Report a max size exceed error and disconnect the first time this is called.
        """
        if not self.deferred.called:
            self.deferred.errback(BodyExceededMaxSize())
            # Close the connection (forcefully) since all the data will get
            # discarded anyway.
            self.transport.abortConnection()

    def dataReceived(self, data) -> None:
        self._maybe_fail()

    def connectionLost(self, reason) -> None:
        self._maybe_fail()


class _ReadBodyWithMaxSizeProtocol(protocol.Protocol):
    """A protocol which reads body to a stream, erroring if the body exceeds a maximum size."""

    def __init__(self, deferred, max_size):
        self.stream = BytesIO()
        self.deferred = deferred
        self.length = 0
        self.max_size = max_size

    def dataReceived(self, data) -> None:
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
            self.transport.abortConnection()

    def connectionLost(self, reason = connectionDone) -> None:
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


def read_body_with_max_size(response, max_size):
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
    d = defer.Deferred()

    # If the Content-Length header gives a size larger than the maximum allowed
    # size, do not bother downloading the body.
    if max_size is not None and response.length != UNKNOWN_LENGTH:
        if response.length > max_size:
            response.deliverBody(_DiscardBodyWithMaxSizeProtocol(d))
            return d

    response.deliverBody(_ReadBodyWithMaxSizeProtocol(d, max_size))
    return d
