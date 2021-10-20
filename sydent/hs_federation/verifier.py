# Copyright 2018 New Vector Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import time
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, cast

import attr
import signedjson.key
import signedjson.sign
from signedjson.sign import SignatureVerifyException
from twisted.web.server import Request
from unpaddedbase64 import decode_base64

from sydent.hs_federation.types import (
    CachedVerificationKeys,
    SignedMatrixRequest,
    VerifyKeys,
)
from sydent.http.httpclient import FederationHttpClient
from sydent.types import JsonDict
from sydent.util.stringutils import is_valid_matrix_server_name

if TYPE_CHECKING:
    from sydent.sydent import Sydent

logger = logging.getLogger(__name__)


class NoAuthenticationError(Exception):
    """
    Raised when no signature is provided that could be authenticated
    """

    pass


class InvalidServerName(Exception):
    """
    Raised when the provided origin parameter is not a valid hostname (plus optional port).
    """

    pass


class Verifier:
    """
    Verifies signed json blobs from Matrix Homeservers by finding the
    homeserver's address, contacting it, requesting its keys and
    verifying that the signature on the json blob matches.
    """

    def __init__(self, sydent: "Sydent") -> None:
        self.sydent = sydent
        # Cache of server keys. These are cached until the 'valid_until_ts' time
        # in the result.
        self.cache: Dict[str, CachedVerificationKeys] = {
            # server_name: <result from keys query>,
        }

    async def _getKeysForServer(self, server_name: str) -> VerifyKeys:
        """Get the signing key data from a homeserver.

        :param server_name: The name of the server to request the keys from.

        :return: The verification keys returned by the server.
        """

        if server_name in self.cache:
            cached = self.cache[server_name]
            now = int(time.time() * 1000)
            if cached.valid_until_ts > now:
                return cached.verify_keys

        client = FederationHttpClient(self.sydent)
        # Cast safety: we have validation logic below which checks that
        # - `verify_keys` is present
        # - `valid_until_ts` is an integer if present
        # - cached entries always have a `valid_until_ts` key
        # and we don't use any of the other fields on GetKeyResponse.
        # The only use of the cache is in this function, and only to read
        # the two fields mentioned above.
        result = await client.get_json(
            "matrix://%s/_matrix/key/v2/server/" % server_name, 1024 * 50
        )
        if "verify_keys" not in result:
            raise SignatureVerifyException("No key found in response")

        if not isinstance(result["verify_keys"], dict):
            raise SignatureVerifyException(
                f"Invalid type for verify_keys: expected dict, got {result['verify_keys']}"
            )

        keys_to_remove = []
        for key_name, key_dict in result["verify_keys"].items():
            if "key" not in key_dict:
                logger.warning("Ignoring key %s with no 'key'", key_name)
                keys_to_remove.append(key_name)
            elif not isinstance(key_dict["key"], str):
                raise SignatureVerifyException(
                    f"Invalid type for verify_keys/{key_name}/key: "
                    f"expected str, got {key_dict['key']}"
                )
        for key_name in keys_to_remove:
            del result["verify_keys"][key_name]

        # We've now verified that verify_keys has the correct type.
        verify_keys: VerifyKeys = result["verify_keys"]

        if "valid_until_ts" in result:
            if not isinstance(result["valid_until_ts"], int):
                raise SignatureVerifyException(
                    "Invalid valid_until_ts received, must be an integer"
                )

            # Don't cache anything without a valid_until_ts or we wouldn't
            # know when to expire it.

            logger.info(
                "Got keys for %s: caching until %d",
                server_name,
                result["valid_until_ts"],
            )
            self.cache[server_name] = CachedVerificationKeys(
                verify_keys, result["valid_until_ts"]
            )

        return verify_keys

    async def verifyServerSignedJson(
        self,
        signed_json: SignedMatrixRequest,
        acceptable_server_names: Optional[List[str]] = None,
    ) -> Tuple[str, str]:
        """Given a signed json object, try to verify any one
        of the signatures on it

        XXX: This contains a fairly noddy version of the home server
        SRV lookup and signature verification. It does no caching (just
        fetches the signature each time and does not contact any other
        servers to do perspective checks).

        :param acceptable_server_names: If provided and not None,
        only signatures from servers in this list will be accepted.

        :return a tuple of the server name and key name that was
        successfully verified.

        :raise SignatureVerifyException: The json cannot be verified.
        """
        for server_name, sigs in signed_json.signatures.items():
            if acceptable_server_names is not None:
                if server_name not in acceptable_server_names:
                    continue

            server_keys = await self._getKeysForServer(server_name)
            for key_name, sig in sigs.items():
                if key_name in server_keys:

                    key_bytes = decode_base64(server_keys[key_name]["key"])
                    verify_key = signedjson.key.decode_verify_key_bytes(
                        key_name, key_bytes
                    )
                    logger.info("verifying sig from key %r", key_name)
                    payload = attr.asdict(signed_json)
                    signedjson.sign.verify_signed_json(payload, server_name, verify_key)
                    logger.info(
                        "Verified signature with key %s from %s", key_name, server_name
                    )
                    return (server_name, key_name)
            logger.warning(
                "No matching key found for signature block %r in server keys %r",
                signed_json.signatures,
                server_keys,
            )
        logger.warning(
            "Unable to verify any signatures from block %r. Acceptable server names: %r",
            signed_json.signatures,
            acceptable_server_names,
        )
        raise SignatureVerifyException("No matching signature found")

    async def authenticate_request(self, request: "Request", content: JsonDict) -> str:
        """Authenticates a Matrix federation request based on the X-Matrix header
        XXX: Copied largely from synapse

        :param request: The request object to authenticate
        :param content: The content of the request, if any

        :return: The origin of the server whose signature was validated
        """
        auth_headers = request.requestHeaders.getRawHeaders("Authorization")
        if not auth_headers:
            raise NoAuthenticationError("Missing Authorization headers")

        # Retrieve an origin and signatures from the authorization header.
        origin = None
        signatures: Dict[str, Dict[str, str]] = {}
        for auth in auth_headers:
            if auth.startswith("X-Matrix"):
                (origin, key, sig) = parse_auth_header(auth)
                signatures.setdefault(origin, {})[key] = sig

        if origin is None:
            raise NoAuthenticationError("Missing X-Matrix Authorization header")
        if not is_valid_matrix_server_name(origin):
            raise InvalidServerName(
                "X-Matrix header's origin parameter must be a valid Matrix server name"
            )

        json_request = SignedMatrixRequest(
            method=request.method,
            uri=request.uri,
            destination_is=self.sydent.config.general.server_name,
            signatures=signatures,
            origin=origin,
            content=content,
        )
        await self.verifyServerSignedJson(json_request, [origin])

        logger.info("Verified request from HS %s", origin)

        return origin


def parse_auth_header(header_str: str) -> Tuple[str, str, str]:
    """
    Extracts a server name, signing key and payload signature from an
    "Authorization: X-Matrix ..." header.

    :param header_str: The content of the header, Starting at "X-Matrix".
        For example, `X-Matrix origin=origin.example.com,key="ed25519:key1",sig="ABCDEF..."`
        See https://matrix.org/docs/spec/server_server/r0.1.4#request-authentication

    :return: The server name, the signing key, and the payload signature.

    :raises SignatureVerifyException: if the header did not meet the expected format.
    """
    try:
        # Strip off "X-Matrix " and break up into key-value pairs.
        params = header_str.split(" ")[1].split(",")
        param_dict: Dict[str, str] = dict(
            # Cast safety: the split() call will either return a 1- or 2- tuple.
            # If it returns a 1-tuple, dict() will complain with a ValueError
            # so we'll spot the bad header.
            cast(Tuple[str, str], kv.split("=", maxsplit=1))
            for kv in params
        )

        def strip_quotes(value: str) -> str:
            if value.startswith('"'):
                return value[1:-1]
            else:
                return value

        origin = strip_quotes(param_dict["origin"])
        key = strip_quotes(param_dict["key"])
        sig = strip_quotes(param_dict["sig"])
        return origin, key, sig
    except Exception:
        raise SignatureVerifyException("Malformed Authorization header")
