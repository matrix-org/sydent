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

from twisted.internet import defer
from twisted.names.error import DNSNameError
import twisted.names.client
from unpaddedbase64 import decode_base64
import signedjson.sign
import signedjson.key
from signedjson.sign import SignatureVerifyException

from sydent.http.httpclient import FederationHttpClient


logger = logging.getLogger(__name__)

"""
Verifies signed json blobs from Matrix Homeservers by finding the
Homeserver's address, contacting it, requesting its keys and
verifying that the signature on the json blob matches.
"""
class Verifier(object):
    def __init__(self, sydent):
        self.sydent = sydent

    @defer.inlineCallbacks
    def _getEndpointForServer(self, server_name):
        if ':' in server_name:
            defer.returnValue(tuple(server_name.rsplit(':', 1)))

        service_name = "_%s._%s.%s" % ('_matrix', '_tcp', server_name)

        default = server_name, 8448

        try:
            answers, _, _ = yield twisted.names.client.lookupService(service_name)
        except DNSNameError:
            defer.returnValue(default)

        for answer in answers:
            if answer.type != dns.SRV or not answer.payload:
                continue

            # XXX we just use the first
            defer.returnValue(str(answer.payload.target), answer.payload.port)

        defer.returnValue(default)

    @defer.inlineCallbacks
    def _getKeysForServer(self, server_name):
        """Get the signing key data from a home server.
        """
        host_port = yield self._getEndpointForServer(server_name)
        logger.info("Got host/port %s/%s for %s", host_port[0], host_port[1], server_name)
        client = FederationHttpClient(self.sydent)
        result = yield client.get_json("https://%s:%s/_matrix/key/v2/server/" % host_port)
        if 'verify_keys' not in result:
            raise Exception("No key found in response")
        defer.returnValue(result['verify_keys'])

    @defer.inlineCallbacks
    def verifyServerSignedJson(self, signed_json, acceptable_server_names=None):
        """Given a signed json object, try to verify any one
        of the signatures on it
        XXX: This contains a very noddy version of the home server
        SRV lookup and signature verification. It forms HTTPS URLs
        from the result of the SRV lookup which will mean the Host:
        parameter in the request will be wrong. It only looks at
        the first SRV result. It does no caching (just fetches the
        signature each time and does not contact any other servers
        to do perspectives checks.

        :param acceptable_server_names If provided and not None,
        only signatures from servers in this list will be accepted.

        :return a tuple of the server name and key name that was
        successfully verified. If the json cannot be verified,
        raises SignatureVerifyException.
        """
        if 'signatures' not in signed_json:
            raise SignatureVerifyException()
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
                    signedjson.sign.verify_signed_json(signed_json, server_name, verify_key)
                    logger.info("Verified signature with key %s from %s", key_name, server_name)
                    defer.returnValue((server_name, key_name))
        logger.warn("No matching key found for signature block %r", signed_json['signatures'])
        raise SignatureVerifyException()
