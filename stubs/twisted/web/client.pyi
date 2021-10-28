from typing import Any, BinaryIO, Optional, Type, TypeVar

import twisted.internet
from twisted.internet.defer import Deferred
from twisted.internet.interfaces import (
    IConsumer,
    IOpenSSLClientConnectionCreator,
    IProtocol,
)
from twisted.internet.task import Cooperator
from twisted.web.http_headers import Headers
from twisted.web.iweb import (
    IAgent,
    IAgentEndpointFactory,
    IBodyProducer,
    IPolicyForHTTPS,
    IResponse,
)
from zope.interface import implementer

C = TypeVar("C")

@implementer(IPolicyForHTTPS)
class BrowserLikePolicyForHTTPS:
    def creatorForNetloc(
        self, hostname: bytes, port: int
    ) -> IOpenSSLClientConnectionCreator: ...

class HTTPConnectionPool:
    persistent: bool
    maxPersistentPerHost: int
    cachedConnectionTimeout: float
    retryAutomatically: bool
    def __init__(self, reactor: object, persistent: bool = True): ...

@implementer(IAgent)
class Agent:
    # Here and in `usingEndpointFactory`, reactor should be a "provider of
    # L{IReactorTCP}, L{IReactorTime} and either
    # L{IReactorPluggableNameResolver} or L{IReactorPluggableResolver}."
    # I don't know how to encode that in the type system; see also
    # https://github.com/Shoobx/mypy-zope/issues/58
    def __init__(
        self,
        reactor: object,
        contextFactory: IPolicyForHTTPS = BrowserLikePolicyForHTTPS(),
        connectTimeout: Optional[float] = None,
        bindAddress: Optional[bytes] = None,
        pool: Optional[HTTPConnectionPool] = None,
    ): ...
    def request(
        self,
        method: bytes,
        uri: bytes,
        headers: Optional[Headers] = None,
        bodyProducer: Optional[IBodyProducer] = None,
    ) -> Deferred[IResponse]: ...
    @classmethod
    def usingEndpointFactory(
        cls: Type[C],
        reactor: object,
        endpointFactory: IAgentEndpointFactory,
        pool: Optional[HTTPConnectionPool] = None,
    ) -> C: ...

@implementer(IBodyProducer)
class FileBodyProducer:
    def __init__(
        self,
        inputFile: BinaryIO,
        cooperator: Cooperator = ...,
        readSize: int = 2 ** 16,
    ): ...
    # Length is either `int` or the opaque object UNKNOWN_LENGTH.
    length: int | object
    def startProducing(self, consumer: IConsumer) -> Deferred[None]: ...
    def stopProducing(self) -> None: ...
    def pauseProducing(self) -> None: ...
    def resumeProducing(self) -> None: ...

def readBody(response: IResponse) -> Deferred[bytes]: ...

# Type ignore: I don't want to respecify the methods on the interface that we
# don't use.
@implementer(IResponse)  # type: ignore[misc]
class Response:
    code: int
    headers: Headers
    # Length is either `int` or the opaque object UNKNOWN_LENGTH.
    length: int | object
    def deliverBody(self, protocol: IProtocol) -> None: ...

class ResponseDone: ...

class URI:
    scheme: bytes
    netloc: bytes
    host: bytes
    port: int
    path: bytes
    params: bytes
    query: bytes
    fragment: bytes
    def __init__(
        self,
        scheme: bytes,
        netloc: bytes,
        host: bytes,
        port: int,
        path: bytes,
        params: bytes,
        query: bytes,
        fragment: bytes,
    ): ...
    @classmethod
    def fromBytes(cls: Type[C], uri: bytes, defaultPort: Optional[int] = None) -> C: ...

@implementer(IAgent)
class RedirectAgent:
    def __init__(self, Agent: Agent, redirectLimit: int = 20): ...
    def request(
        self,
        method: bytes,
        uri: bytes,
        headers: Optional[Headers] = None,
        bodyProducer: Optional[IBodyProducer] = None,
    ) -> Deferred[IResponse]: ...
