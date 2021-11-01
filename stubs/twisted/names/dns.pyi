from typing import ClassVar, Generic, Optional, TypeVar

class Name:
    name: bytes
    def __init__(self, name: bytes = ...): ...

SRV: int

class Record_SRV:
    priority: int
    weight: int
    port: int
    target: Name
    ttl: int

_Payload = TypeVar("_Payload")  # should be bound to IEncodableRecord

class RRHeader(Generic[_Payload]):
    fmt: ClassVar[str]
    name: Name
    type: int
    cls: int
    ttl: int
    payload: Optional[_Payload]
    auth: bool
