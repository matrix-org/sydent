from typing import Any, Optional

class ConnectError(Exception):
    def __init__(self, osError: Optional[Any] = ..., string: str = ...): ...
