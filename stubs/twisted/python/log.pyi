from typing import Any, Dict, Optional, Union

from twisted.python.failure import Failure

EventDict = Dict[str, Any]

def err(
    _stuff: Union[None, Exception, Failure] = None,
    _why: Optional[str] = None,
    **kw: object,
) -> None: ...

class PythonLoggingObserver:
    def emit(self, eventDict: EventDict) -> None:
        """
        Emit the given log event.

        @param eventDict: a log event
        """
    def start(self) -> None: ...
    def stop(self) -> None: ...
