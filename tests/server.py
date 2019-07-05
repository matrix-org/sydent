# -*- coding: utf-8 -*-
# Copyright 2019 The Matrix.org Foundation C.I.C.
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

import attr
from zope.interface import implementer

from twisted.internet import address, udp
from twisted.internet._resolver import SimpleResolverComplexifier
from twisted.internet.defer import Deferred, fail, succeed
from twisted.internet.error import DNSLookupError
from twisted.internet.interfaces import IReactorPluggableNameResolver, IResolverSimple
from twisted.python.failure import Failure
from twisted.test.proto_helpers import MemoryReactorClock
from twisted.web.http_headers import Headers

from tests.utils import setup_test_identity_server as _sti

logger = logging.getLogger(__name__)


class TimedOutException(Exception):
    """
    A web query timed out.
    """


@attr.s
class FakeChannel(object):
    """
    A fake Twisted Web Channel (the part that interfaces with the
    wire).
    """

    _reactor = attr.ib()
    result = attr.ib(default=attr.Factory(dict))
    _producer = None

    @property
    def json_body(self):
        if not self.result:
            raise Exception("No result yet.")
        return json.loads(self.result["body"].decode('utf8'))

    @property
    def code(self):
        if not self.result:
            raise Exception("No result yet.")
        return int(self.result["code"])

    @property
    def headers(self):
        if not self.result:
            raise Exception("No result yet.")
        h = Headers()
        for i in self.result["headers"]:
            h.addRawHeader(*i)
        return h

    def writeHeaders(self, version, code, reason, headers):
        self.result["version"] = version
        self.result["code"] = code
        self.result["reason"] = reason
        self.result["headers"] = headers

    def write(self, content):
        assert isinstance(content, bytes), "Should be bytes! " + repr(content)

        if "body" not in self.result:
            self.result["body"] = b""

        self.result["body"] += content

    def registerProducer(self, producer, streaming):
        self._producer = producer
        self.producerStreaming = streaming

        def _produce():
            if self._producer:
                self._producer.resumeProducing()
                self._reactor.callLater(0.1, _produce)

        if not streaming:
            self._reactor.callLater(0.0, _produce)

    def unregisterProducer(self):
        if self._producer is None:
            return

        self._producer = None

    def requestDone(self, _self):
        self.result["done"] = True

    def getPeer(self):
        # We give an address so that getClientIP returns a non null entry,
        # causing us to record the MAU
        return address.IPv4Address("TCP", "127.0.0.1", 3423)

    def getHost(self):
        return None

    @property
    def transport(self):
        return self


class FakeSite:
    """
    A fake Twisted Web Site, with mocks of the extra things that
    Synapse adds.
    """

    server_version_string = b"1"
    site_tag = "test"
    access_logger = logging.getLogger("synapse.access.http.fake")


def wait_until_result(clock, request, timeout=100):
    """
    Wait until the request is finished.
    """
    clock.run()
    x = 0

    while not request.finished:

        # If there's a producer, tell it to resume producing so we get content
        if request._channel._producer:
            request._channel._producer.resumeProducing()

        x += 1

        if x > timeout:
            raise TimedOutException("Timed out waiting for request to finish.")

        clock.advance(0.1)


def render(request, resource, clock):
    request.render(resource)
    wait_until_result(clock, request)


@implementer(IReactorPluggableNameResolver)
class ThreadedMemoryReactorClock(MemoryReactorClock):
    """
    A MemoryReactorClock that supports callFromThread.
    """

    def __init__(self):
        self.threadpool = ThreadPool(self)

        self._udp = []
        lookups = self.lookups = {}

        @implementer(IResolverSimple)
        class FakeResolver(object):
            def getHostByName(self, name, timeout=None):
                if name not in lookups:
                    return fail(DNSLookupError("OH NO: unknown %s" % (name,)))
                return succeed(lookups[name])

        self.nameResolver = SimpleResolverComplexifier(FakeResolver())
        super(ThreadedMemoryReactorClock, self).__init__()

    def listenUDP(self, port, protocol, interface='', maxPacketSize=8196):
        p = udp.Port(port, protocol, interface, maxPacketSize, self)
        p.startListening()
        self._udp.append(p)
        return p

    def callFromThread(self, callback, *args, **kwargs):
        """
        Make the callback fire in the next reactor iteration.
        """
        d = Deferred()
        d.addCallback(lambda x: callback(*args, **kwargs))
        self.callLater(0, d.callback, True)
        return d

    def getThreadPool(self):
        return self.threadpool


class ThreadPool:
    """
    Threadless thread pool.
    """

    def __init__(self, reactor):
        self._reactor = reactor

    def start(self):
        pass

    def stop(self):
        pass

    def callInThreadWithCallback(self, onResult, function, *args, **kwargs):
        def _(res):
            if isinstance(res, Failure):
                onResult(False, res)
            else:
                onResult(True, res)

        d = Deferred()
        d.addCallback(lambda x: function(*args, **kwargs))
        d.addBoth(_)
        self._reactor.callLater(0, d.callback, True)
        return d


def setup_test_identity_server(*args, **kwargs):
    """
    Set up a synchronous test server, driven by the reactor used by
    the homeserver.
    """
    return _sti(*args, **kwargs)


@attr.s(cmp=False)
class FakeTransport(object):
    """
    A twisted.internet.interfaces.ITransport implementation which sends all its data
    straight into an IProtocol object: it exists to connect two IProtocols together.

    To use it, instantiate it with the receiving IProtocol, and then pass it to the
    sending IProtocol's makeConnection method:

        server = HTTPChannel()
        client.makeConnection(FakeTransport(server, self.reactor))

    If you want bidirectional communication, you'll need two instances.
    """

    other = attr.ib()
    """The Protocol object which will receive any data written to this transport.

    :type: twisted.internet.interfaces.IProtocol
    """

    _reactor = attr.ib()
    """Test reactor

    :type: twisted.internet.interfaces.IReactorTime
    """

    _protocol = attr.ib(default=None)
    """The Protocol which is producing data for this transport. Optional, but if set
    will get called back for connectionLost() notifications etc.
    """

    disconnecting = False
    disconnected = False
    buffer = attr.ib(default=b'')
    producer = attr.ib(default=None)
    autoflush = attr.ib(default=True)

    def getPeer(self):
        return None

    def getHost(self):
        return None

    def loseConnection(self, reason=None):
        if not self.disconnecting:
            logger.info("FakeTransport: loseConnection(%s)", reason)
            self.disconnecting = True
            if self._protocol:
                self._protocol.connectionLost(reason)
            self.disconnected = True

    def abortConnection(self):
        logger.info("FakeTransport: abortConnection()")
        self.loseConnection()

    def pauseProducing(self):
        if not self.producer:
            return

        self.producer.pauseProducing()

    def resumeProducing(self):
        if not self.producer:
            return
        self.producer.resumeProducing()

    def unregisterProducer(self):
        if not self.producer:
            return

        self.producer = None

    def registerProducer(self, producer, streaming):
        self.producer = producer
        self.producerStreaming = streaming

        def _produce():
            d = self.producer.resumeProducing()
            d.addCallback(lambda x: self._reactor.callLater(0.1, _produce))

        if not streaming:
            self._reactor.callLater(0.0, _produce)

    def write(self, byt):
        self.buffer = self.buffer + byt

        # always actually do the write asynchronously. Some protocols (notably the
        # TLSMemoryBIOProtocol) get very confused if a read comes back while they are
        # still doing a write. Doing a callLater here breaks the cycle.
        if self.autoflush:
            self._reactor.callLater(0.0, self.flush)

    def writeSequence(self, seq):
        for x in seq:
            self.write(x)

    def flush(self, maxbytes=None):
        if not self.buffer:
            # nothing to do. Don't write empty buffers: it upsets the
            # TLSMemoryBIOProtocol
            return

        if self.disconnected:
            return

        if getattr(self.other, "transport") is None:
            # the other has no transport yet; reschedule
            if self.autoflush:
                self._reactor.callLater(0.0, self.flush)
            return

        if maxbytes is not None:
            to_write = self.buffer[:maxbytes]
        else:
            to_write = self.buffer

        logger.info("%s->%s: %s", self._protocol, self.other, to_write)

        try:
            self.other.dataReceived(to_write)
        except Exception as e:
            logger.warning("Exception writing to protocol: %s", e)
            return

        self.buffer = self.buffer[len(to_write) :]
        if self.buffer and self.autoflush:
            self._reactor.callLater(0.0, self.flush)
