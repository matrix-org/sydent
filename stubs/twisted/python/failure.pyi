from types import TracebackType
from typing import Type, Optional


class Failure(BaseException):

    def __init__(
        self,
        exc_value: Optional[BaseException] = None,
        exc_type: Optional[Type[BaseException]] = None,
        exc_tb: Optional[TracebackType] = None,
        captureVars: bool = False,
    ):
        ...
