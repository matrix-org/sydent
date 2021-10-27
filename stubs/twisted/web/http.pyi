import typing
from typing import AnyStr, Optional, Dict, List

from twisted.internet.defer import Deferred
from twisted.internet.interfaces import ITCPTransport, IAddress
from twisted.logger import Logger
from twisted.web.http_headers import Headers

class HTTPChannel: ...

class Request:
    # Instance attributes mentioned in the docstring
    method: bytes
    uri: bytes
    path: bytes
    args: Dict[bytes, List[bytes]]
    content: typing.BinaryIO
    cookies: List[bytes]
    requestHeaders: Headers
    responseHeaders: Headers
    notifications: List[Deferred[None]]
    _disconnected: bool
    _log: Logger

    # Other instance attributes set in __init__
    channel: HTTPChannel
    client: IAddress
    # This was hard to derive.
    # - `transport` is `self.channel.transport`
    # - `self.channel` is set in the constructor, and looks like it's always
    #   an `HTTPChannel`.
    # - `HTTPChannel` is a `LineReceiver` is a `Protocol` is a `BaseProtocol`.
    # - `BaseProtocol` sets `self.transport` to initially `None`.
    #
    # Note that `transport` is set to an ITransport in makeConnection,
    # so is almost certainly not None by the time it reaches our code.
    #
    # I've narrowed this to ITCPTransport because
    # - we use `self.transport.abortConnection`, which belongs to that interface
    # - twisted does too! in its implementation of HTTPChannel.forceAbortClient
    transport: Optional[ITCPTransport]


    def getHeader(self, key: AnyStr) -> Optional[AnyStr]: ...

    def handleContentChunk(self, data: bytes) -> None: ...

class PotentialDataLoss(Exception): ...
