from typing import BinaryIO, Any, Optional

import twisted.internet
from twisted.internet.defer import Deferred
from twisted.internet.interfaces import (
    IOpenSSLClientConnectionCreator,
    IConsumer,
    IProtocol,
)
from twisted.internet.task import Cooperator
from twisted.web.http_headers import Headers

from twisted.web.iweb import IResponse, IAgent, IBodyProducer, IPolicyForHTTPS
from zope.interface import implementer

@implementer(IPolicyForHTTPS)
class BrowserLikePolicyForHTTPS:
    def creatorForNetloc(
        self, hostname: bytes, port: int
    ) -> IOpenSSLClientConnectionCreator: ...

class HTTPConnectionPool: ...

@implementer(IAgent)
class Agent:
    def __init__(
        self,
        reactor: Any,
        contextFactory: IPolicyForHTTPS = BrowserLikePolicyForHTTPS(),
        connectTimeout: Optional[float] = None,
        bindAddress: Optional[bytes] = None,
        pool: Optional[HTTPConnectionPool] = None,
    ): ...
    # Type safety: IAgent says this returns a Deferred[IResponse].
    # I'm narrowing it here (but that's not strictly allowed because Deferred[T]
    # is _contra_variant in T. It's all muddling.
    def request(  # type: ignore[override]
        self,
        method: bytes,
        uri: bytes,
        headers: Optional[Headers] = None,
        bodyProducer: Optional[IBodyProducer] = None,
    ) -> Deferred[Response]: ...

@implementer(IBodyProducer)
class FileBodyProducer:
    def __init__(
        self,
        inputFile: BinaryIO,
        # Type safety: twisted.internet.task.cooperate is a function with the
        # same signature as Cooperator.cooperate. (It just wraps a module-level
        # global cooperator.) But there's no easy way to annotate "either this
        # type or a specific module".
        cooperator: Cooperator = twisted.internet.task,  # type: ignore[assignment]
        readSize: int = 2 ** 16,
    ): ...
    # Length is either `int` or the opaque object UNKNOWN_LENGTH.
    length: int | object
    def startProducing(self, consumer: IConsumer) -> Deferred[None]: ...
    def stopProducing(self) -> None: ...
    def pauseProducing(self) -> None: ...
    def resumeProducing(self) -> None: ...

def readBody(response: IResponse) -> Deferred[bytes]: ...

class Response:
    code: int
    headers: Headers
    # Length is either `int` or the opaque object UNKNOWN_LENGTH.
    length: int | object
    def deliverBody(self, protocol: IProtocol) -> None: ...

class ResponseDone: ...
