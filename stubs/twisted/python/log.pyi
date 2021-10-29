from typing import Any, Dict, Optional, Union

from twisted.python.failure import Failure

EventDict = Dict[str, Any]

def err(
    _stuff: Union[None, Exception, Failure] = ...,
    _why: Optional[str] = ...,
    **kw: object,
) -> None: ...

class PythonLoggingObserver:
    def emit(self, eventDict: EventDict) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
