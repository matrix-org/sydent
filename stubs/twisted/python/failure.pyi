from types import TracebackType
from typing import Optional, Type, TypeVar, Union, overload

_E = TypeVar("_E")

class Failure(BaseException):
    def __init__(
        self,
        exc_value: Optional[BaseException] = ...,
        exc_type: Optional[Type[BaseException]] = ...,
        exc_tb: Optional[TracebackType] = ...,
        captureVars: bool = ...,
    ): ...
    @overload
    def check(self, singleErrorType: Type[_E]) -> Optional[_E]: ...
    @overload
    def check(
        self, *errorTypes: Union[str, Type[Exception]]
    ) -> Optional[Exception]: ...
    def getTraceback(
        self,
        elideFrameworkCode: int = ...,
        detail: str = ...,
    ) -> str: ...
