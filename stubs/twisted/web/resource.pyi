from typing import ClassVar

from zope.interface import Interface, implementer

class IResource(Interface):
    isLeaf: ClassVar[bool]
    def __init__() -> None: ...
    def putChild(path: bytes, child: IResource) -> None: ...

@implementer(IResource)
class Resource:
    isLeaf: ClassVar[bool]
    def putChild(self, path: bytes, child: IResource) -> None: ...
