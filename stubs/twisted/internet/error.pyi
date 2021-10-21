from typing import Optional, Any


class ConnectError(Exception):
    def __init__(self, osError: Optional[Any] = None, string: str = ""): ...