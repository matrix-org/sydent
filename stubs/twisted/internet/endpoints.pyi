from typing import AnyStr, Optional

from twisted.internet import interfaces
from twisted.internet.defer import Deferred
from twisted.internet.interfaces import (
    IOpenSSLClientConnectionCreator,
    IProtocol,
    IProtocolFactory,
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
        timeout: float = ...,
        bindAddress: Optional[bytes] = ...,
        attemptDelay: Optional[float] = ...,
    ): ...
    def connect(self, protocol_factory: IProtocolFactory) -> Deferred[IProtocol]: ...

def wrapClientTLS(
    connectionCreator: IOpenSSLClientConnectionCreator,
    wrappedEndpoint: IStreamClientEndpoint,
) -> IStreamClientEndpoint: ...
