from typing import AnyStr, Optional


class Request:
    def getHeader(self, key: AnyStr) -> Optional[AnyStr]: ...
