from typing import BinaryIO, Optional, Sequence, Type, TypeVar

from twisted.internet.defer import Deferred
from twisted.internet.interfaces import IConsumer, IProtocol
from twisted.internet.task import Cooperator
from twisted.python.failure import Failure
from twisted.web.http_headers import Headers
from twisted.web.iweb import (
    IAgent,
    IAgentEndpointFactory,
    IBodyProducer,
    IPolicyForHTTPS,
    IResponse,
)
from zope.interface import implementer

_C = TypeVar("_C")

class ResponseFailed(Exception):
    def __init__(
        self, reasons: Sequence[Failure], response: Optional[Response] = ...
    ): ...

class HTTPConnectionPool:
    persistent: bool
    maxPersistentPerHost: int
    cachedConnectionTimeout: float
    retryAutomatically: bool
    def __init__(self, reactor: object, persistent: bool = ...): ...

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
        contextFactory: IPolicyForHTTPS = ...,
        connectTimeout: Optional[float] = ...,
        bindAddress: Optional[bytes] = ...,
        pool: Optional[HTTPConnectionPool] = ...,
    ): ...
    def request(
        self,
        method: bytes,
        uri: bytes,
        headers: Optional[Headers] = ...,
        bodyProducer: Optional[IBodyProducer] = ...,
    ) -> Deferred[IResponse]: ...
    @classmethod
    def usingEndpointFactory(
        cls: Type[_C],
        reactor: object,
        endpointFactory: IAgentEndpointFactory,
        pool: Optional[HTTPConnectionPool] = ...,
    ) -> _C: ...

@implementer(IBodyProducer)
class FileBodyProducer:
    def __init__(
        self,
        inputFile: BinaryIO,
        cooperator: Cooperator = ...,
        readSize: int = ...,
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
    def fromBytes(
        cls: Type[_C], uri: bytes, defaultPort: Optional[int] = ...
    ) -> _C: ...

@implementer(IAgent)
class RedirectAgent:
    def __init__(self, agent: Agent, redirectLimit: int = ...): ...
    def request(
        self,
        method: bytes,
        uri: bytes,
        headers: Optional[Headers] = ...,
        bodyProducer: Optional[IBodyProducer] = ...,
    ) -> Deferred[IResponse]: ...
