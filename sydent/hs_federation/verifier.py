# -*- coding: utf-8 -*-

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

from twisted.internet import defer
from twisted.names.error import DNSNameError
import twisted.names.client
import twisted.names.dns
from unpaddedbase64 import decode_base64
import signedjson.sign
import signedjson.key
from signedjson.sign import SignatureVerifyException

from sydent.http.httpclient import FederationHttpClient


logger = logging.getLogger(__name__)


class NoAuthenticationError(Exception):
    """
    Raised when no signature is provided that could be authenticated
    """
    pass


class Verifier(object):
    """
    Verifies signed json blobs from Matrix Homeservers by finding the
    homeserver's address, contacting it, requesting its keys and
    verifying that the signature on the json blob matches.
    """
    def __init__(self, sydent):
        self.sydent = sydent
        # Cache of server keys. These are cached until the 'valid_until_ts' time
        # in the result.
        self.cache = {
            # server_name: <result from keys query>,
        }

    @defer.inlineCallbacks
    def _getKeysForServer(self, server_name):
        """Get the signing key data from a home server.
        """

        if server_name in self.cache:
            cached = self.cache[server_name]
            now = int(time.time() * 1000)
            if cached['valid_until_ts'] > now:
                defer.returnValue(self.cache[server_name]['verify_keys'])

        client = FederationHttpClient(self.sydent)
        result = yield client.get_json("matrix://%s/_matrix/key/v2/server/" % server_name)
        if 'verify_keys' not in result:
            raise SignatureVerifyException("No key found in response")

        if 'valid_until_ts' in result:
            # Don't cache anything without a valid_until_ts or we wouldn't
            # know when to expire it.
            logger.info("Got keys for %s: caching until %s", server_name, result['valid_until_ts'])
            self.cache[server_name] = result

        defer.returnValue(result['verify_keys'])

    @defer.inlineCallbacks
    def verifyServerSignedJson(self, signed_json, acceptable_server_names=None):
        """Given a signed json object, try to verify any one
        of the signatures on it
        XXX: This contains a fairly noddy version of the home server
        SRV lookup and signature verification. It only looks at
        the first SRV result.

        :param acceptable_server_names: If provided and not None,
        only signatures from servers in this list will be accepted.
        :type acceptable_server_names: list of strings

        :return a tuple of the server name and key name that was
        successfully verified. If the json cannot be verified,
        raises SignatureVerifyException.
        """
        if 'signatures' not in signed_json:
            raise SignatureVerifyException("Signature missing")
        for server_name, sigs in signed_json['signatures'].items():
            if acceptable_server_names is not None:
                if server_name not in acceptable_server_names:
                    continue

            server_keys = yield self._getKeysForServer(server_name)
            for key_name, sig in sigs.items():
                if key_name in server_keys:
                    if 'key' not in server_keys[key_name]:
                        logger.warn("Ignoring key %s with no 'key'")
                        continue
                    key_bytes = decode_base64(server_keys[key_name]['key'])
                    verify_key = signedjson.key.decode_verify_key_bytes(key_name, key_bytes)
                    logger.info("verifying sig from key %r", key_name)
                    signedjson.sign.verify_signed_json(signed_json, server_name, verify_key)
                    logger.info("Verified signature with key %s from %s", key_name, server_name)
                    defer.returnValue((server_name, key_name))
            logger.warn(
                "No matching key found for signature block %r in server keys %r",
                signed_json['signatures'], server_keys,
            )
        logger.warn(
            "Unable to verify any signatures from block %r. Acceptable server names: %r",
            signed_json['signatures'], acceptable_server_names,
        )
        raise SignatureVerifyException("No matching signature found")

    @defer.inlineCallbacks
    def authenticate_request(self, request, content):
        """Authenticates a Matrix federation request based on the X-Matrix header
        XXX: Copied largely from synapse

        :param request: The request object to authenticate
        :param content: The content of the request, if any
        :type content: bytes, None

        :returns: The origin of the server whose signature was validated
        """
        json_request = {
            "method": request.method,
            "uri": request.uri,
            "destination_is": self.sydent.server_name,
            "signatures": {},
        }

        if content is not None:
            json_request["content"] = content

        origin = None

        def parse_auth_header(header_str):
            try:
                params = auth.split(" ")[1].split(",")
                param_dict = dict(kv.split("=") for kv in params)

                def strip_quotes(value):
                    if value.startswith("\""):
                        return value[1:-1]
                    else:
                        return value

                origin = strip_quotes(param_dict["origin"])
                key = strip_quotes(param_dict["key"])
                sig = strip_quotes(param_dict["sig"])
                return (origin, key, sig)
            except Exception:
                raise SignatureVerifyException("Malformed Authorization header")

        auth_headers = request.requestHeaders.getRawHeaders(b"Authorization")

        if not auth_headers:
            raise NoAuthenticationError("Missing Authorization headers")

        for auth in auth_headers:
            if auth.startswith("X-Matrix"):
                (origin, key, sig) = parse_auth_header(auth)
                json_request["origin"] = origin
                json_request["signatures"].setdefault(origin, {})[key] = sig

        if not json_request["signatures"]:
            raise NoAuthenticationError("Missing X-Matrix Authorization header")

        yield self.verifyServerSignedJson(json_request, [origin])

        logger.info("Verified request from HS %s", origin)

        defer.returnValue(origin)
