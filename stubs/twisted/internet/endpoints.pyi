from typing import Optional, AnyStr, Any

from twisted.internet import interfaces
from twisted.internet.defer import Deferred
from twisted.internet.interfaces import (
    IProtocolFactory,
    IProtocol,
    IOpenSSLClientConnectionCreator,
    IStreamClientEndpoint,
)
from zope.interface import implementer

@implementer(interfaces.IStreamClientEndpoint)
class HostnameEndpoint:
    # Reactor should be a "provider of L{IReactorTCP}, L{IReactorTime} and
    # either L{IReactorPluggableNameResolver} or L{IReactorPluggableResolver}."
    # I don't know how to encode that in the type system.
    def __init__(
        self,
        reactor: object,
        host: AnyStr,
        port: int,
        timeout: float = 30,
        bindAddress: Optional[bytes] = None,
        attemptDelay: Optional[float] = None,
    ): ...
    def connect(self, protocol_factory: IProtocolFactory) -> Deferred[IProtocol]: ...

def wrapClientTLS(
    connectionCreator: IOpenSSLClientConnectionCreator,
    wrappedEndpoint: IStreamClientEndpoint,
) -> IStreamClientEndpoint: ...
