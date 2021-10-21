from typing import Dict

import attr
from typing_extensions import TypedDict

from sydent.types import JsonDict


class VerifyKey(TypedDict):
    key: str


VerifyKeys = Dict[str, VerifyKey]


@attr.s(frozen=True, slots=True, auto_attribs=True)
class CachedVerificationKeys:
    verify_keys: VerifyKeys
    valid_until_ts: int


# key: "signing key identifier"; value: signature encoded as unpadded base 64
# See https://spec.matrix.org/unstable/appendices/#signing-details
Signature = Dict[str, str]


@attr.s(frozen=True, slots=True, auto_attribs=True)
class SignedMatrixRequest:
    method: bytes
    uri: bytes
    destination_is: str
    signatures: Dict[str, Signature]
    origin: str
    content: JsonDict
