import typing
from typing import AnyStr, Optional, Dict, List

from twisted.internet.defer import Deferred
from twisted.logger import Logger
from twisted.web.http_headers import Headers


class Request:

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

    def getHeader(self, key: AnyStr) -> Optional[AnyStr]: ...
