from typing import ClassVar, Generic, TypeVar, Optional


class Name:
    name: bytes

    def __init__(self, name: bytes = b""): ...

SRV: int


class Record_SRV:
    priority: int
    weight: int
    port: int
    target: Name
    ttl: int


Payload = TypeVar("Payload")  # should be bound to IEncodableRecord
class RRHeader(Generic[Payload]):
    fmt: ClassVar[str]
    name: Name
    type: int
    cls: int
    ttl: int
    payload: Optional[Payload]
    auth: bool
