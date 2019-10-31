from zope.interface import implementer

from twisted.internet import udp

from twisted.python.failure import Failure
from twisted.internet._resolver import SimpleResolverComplexifier
from twisted.internet.defer import Deferred, fail, succeed
from twisted.internet.error import DNSLookupError
from twisted.internet.interfaces import (
    IReactorPluggableNameResolver,
    IResolverSimple,
)
from twisted.test.proto_helpers import MemoryReactorClock

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

    def listenUDP(self, port, protocol, interface="", maxPacketSize=8196):
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
