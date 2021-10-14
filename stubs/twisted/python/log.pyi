from typing import Optional, Union, Any

from twisted.python.failure import Failure


def err(
    _stuff: Union[None, Exception, Failure] = None,
    _why: Optional[str] = None,
    **kw: Any,
)-> None:
    ...