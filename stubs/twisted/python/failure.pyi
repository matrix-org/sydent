from types import TracebackType
from typing import Optional, Type, TypeVar, Union, overload

E = TypeVar("E")

class Failure(BaseException):
    def __init__(
        self,
        exc_value: Optional[BaseException] = None,
        exc_type: Optional[Type[BaseException]] = None,
        exc_tb: Optional[TracebackType] = None,
        captureVars: bool = False,
    ): ...
    @overload
    def check(self, singleErrorType: Type[E]) -> Optional[E]: ...
    @overload
    def check(
        self, *errorTypes: Union[str, Type[Exception]]
    ) -> Optional[Exception]: ...
    def getTraceback(
        self,
        elideFrameworkCode: int = ...,
        detail: str = ...,
    ) -> str: ...
