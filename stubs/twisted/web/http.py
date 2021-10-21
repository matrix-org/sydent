from typing import AnyStr, Optional

from twisted.internet import interfaces


class Request:
    def getHeader(self, key: AnyStr) -> Optional[AnyStr]: ...
