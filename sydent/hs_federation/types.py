from typing import Dict

from typing_extensions import TypedDict


class _GetKeyResponseRequired(TypedDict):
    """See https://spec.matrix.org/unstable/server-server-api/#get_matrixkeyv2serverkeyid"""

    server_name: str
    verify_keys: "VerifyKeys"


VerifyKeys = Dict[str, "VerifyKey"]


class GetKeyResponse(_GetKeyResponseRequired, total=False):
    old_verify_keys: Dict[str, "OldVerifyKey"]
    signatures: Dict[str, "Signature"]
    valid_until_ts: int


class VerifyKey(TypedDict):
    key: str


class OldVerifyKey(TypedDict):
    expired_ts: int
    key: str


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
