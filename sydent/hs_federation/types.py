from typing import Dict

from typing_extensions import TypedDict
import attr


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


class _SignedMatrixRequestRequired(TypedDict):
    method: bytes
    uri: bytes
    destination_is: str
    signatures: Dict[str, Signature]
    origin: str


class SignedMatrixRequest(_SignedMatrixRequestRequired, total=False):
    content: bytes
