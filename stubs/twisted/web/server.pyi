from typing import Callable, Optional, Type, Union

from twisted.web import http
from twisted.web.resource import IResource

class Request(http.Request): ...

# A requestFactory is allowed to be "[a] factory which is called with (channel)
# and creates L{Request} instances.".
RequestFactory = Callable[[http.HTTPChannel], Request]

# should really inherit from http.HTTPFactory
class Site:
    displayTracebacks: bool
    def __init__(
        self,
        resource: IResource,
        requestFactory: Optional[RequestFactory] = None,
        # Args and kwargs get passed to http.HTTPFactory. But we don't use them.
        *args: object,
        **kwargs: object,
    ): ...
