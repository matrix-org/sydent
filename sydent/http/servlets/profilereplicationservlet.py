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
from twisted.web.resource import Resource
from twisted.internet import defer
from twisted.web import server
from twisted.web.client import readBody
import twisted.names.client
from twisted.names import dns
from twisted.names.error import DNSNameError

import signedjson.sign
import signedjson.key
from signedjson.sign import SignatureVerifyException
from unpaddedbase64 import decode_base64
import json
import logging
from sydent.http.servlets import get_args, jsonwrap
from sydent.db.profiles  import ProfileStore
from sydent.http.httpclient import FederationHttpClient


logger = logging.getLogger(__name__)

MAX_BATCH_SIZE = 200


class ProfileReplicationServlet(Resource):
    isLeaf = True

    def __init__(self, syd):
        self.sydent = syd

    def _getAllowedHomeservers(self):
        rawstr = self.sydent.cfg.get('userdir', 'userdir.allowed_homeservers', '')
        if rawstr == '':
            return []
        return [x.strip() for x in rawstr.split(',')]

    def render_POST(self, request):
        self._async_render_POST(request)
        return server.NOT_DONE_YET

    @defer.inlineCallbacks
    def getEndpointForServer(self, server_name):
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
    def getKeysForServer(self, server_name):
        """Get the signing key data from a home server.
        """
        host_port = yield self.getEndpointForServer(server_name)
        logger.info("Got host/port %s/%s for %s", host_port[0], host_port[1], server_name)
        client = FederationHttpClient(self.sydent)
        result = yield client.get_json("https://%s:%s/_matrix/key/v2/server/" % host_port)
        if 'verify_keys' not in result:
            raise Exception("No key found in response")
        defer.returnValue(result['verify_keys'])

    @defer.inlineCallbacks
    def verifyServerSignedJson(self, signed_json):
        """Given a signed json object, try to verify any one
        of the signatures on it
        XXX: This contains a very noddy version of the home server
        SRV lookup and signature verification. It forms HTTPS URLs
        from the result of the SRV lookup which will mean the Host:
        parameter in the request will be wrong. It only looks at
        the first SRV result. It does no caching (just fetches the
        signature each time and does not contact any other servers
        to do perspectives checks.
        """
        if 'signatures' not in signed_json:
            raise SignatureVerifyException()
        for server_name, sigs in signed_json['signatures'].items():
            server_keys = yield self.getKeysForServer(server_name)
            for key_name, sig in sigs.items():
                if key_name in server_keys:
                    if 'key' not in server_keys[key_name]:
                        logger.warn("Ignoring key %s with no 'key'")
                        continue
                    key_bytes = decode_base64(server_keys[key_name]['key'])
                    verify_key = signedjson.key.decode_verify_key_bytes(key_name, key_bytes)
                    signedjson.sign.verify_signed_json(signed_json, server_name, verify_key)
                    logger.info("Verified signature with key %s from %s", key_name, server_name)
                    defer.returnValue(None)
        logger.warn("No matching key found for signature block %r", signed_json['signatures'])
        raise SignatureVerifyException()

    @defer.inlineCallbacks
    def _async_render_POST(self, request):
        yield
        try:
            body = json.load(request.content)
        except ValueError:
            request.setResponseCode(400)
            request.write(json.dumps({'errcode': 'M_BAD_JSON', 'error': 'Malformed JSON'}))
            request.finish()
            defer.returnValue(None)

        missing = [k for k in ("batchnum", "batch", "origin_server") if k not in body]
        if len(missing) > 0:
            request.setResponseCode(400)
            msg = "Missing parameters: "+(",".join(missing))
            request.write(json.dumps({'errcode': 'M_MISSING_PARAMS', 'error': msg}))
            request.finish()
            defer.returnValue(None)

        try:
            yield self.verifyServerSignedJson(body)
        except SignatureVerifyException:
            request.setResponseCode(403)
            request.write(json.dumps({'errcode': 'M_FORBIDDEN', 'error': 'Signature verification failed'}))
            request.finish()
            defer.returnValue(None)

        batchnum = body["batchnum"]
        batch = body["batch"]
        origin_server = body["origin_server"]

        allowed_hses = self._getAllowedHomeservers()
        if not origin_server in allowed_hses:
            request.setResponseCode(403)
            request.write(json.dumps({'errcode': 'M_FORBIDDEN', 'error': 'origin server not whitelisted'}))
            request.finish()
            defer.returnValue(None)

        profile_store = ProfileStore(self.sydent)

        latest_batch_on_host = profile_store.getLastBatchForOriginServer(origin_server)
        if latest_batch_on_host is None:
            latest_batch_on_host = -1
        if batchnum <= latest_batch_on_host:
            logger.info("Ignoring batch %d from %s: we already have %d", batchnum, origin_server, latest_batch_on_host)
            # we already have this batch, thanks
            request.write(json.dumps({}))
            request.finish()
            defer.returnValue(None)
        elif batchnum == latest_batch_on_host + 1:
            # good, this is the next batch
            if len(batch) > MAX_BATCH_SIZE:
                logger.warn("Host %s sent batch of %s which exceeds max of %d", origin_server, len(batch), MAX_BATCH_SIZE)
                request.setResponseCode(400)
                request.write(json.dumps({'errcode': 'M_UNKNOWN', 'error': 'batch size exceeds max of %d' % (MAX_BATCH_SIZE,)}))
                request.finish()
                defer.returnValue(None)
                
            bad_uids = []
            for uid, info in batch.items():
                if 'display_name' not in info or 'avatar_url' not in info:
                    bad_uids.append(uid)
            if len(bad_uids) > 0:
                logger.warn("Host %s sent batch with missing fields", origin_server)
                request.setResponseCode(400)
                msg = "Missing data for user IDs: %s (required: display_name, avatar_url" % (','.join(bad_uids,))
                request.write(json.dumps({'errcode': 'M_UNKNOWN', 'error': msg}))
                request.finish()
                defer.returnValue(None)

            logger.info("Storing %d profiles in batch %d from %s", len(batch), batchnum, origin_server)
            profile_store.addBatch(origin_server, batchnum, batch)
            request.write((json.dumps({})))
            request.finish()
            defer.returnValue(None)
        else:
            # we've missing a batch, so don't accept this one: they need to be in order
            logger.warn("Rejecting batch %d from %s as we only have %d", batchnum, origin_server, latest_batch_on_host)
            request.setResponseCode(400)
            msg = "Expecting batch %d but got %d" % (latest_batch_on_host + 1, batchnum)
            request.write(json.dumps({'errcode': 'M_UNKNOWN', 'error': msg}))
            request.finish()
            defer.returnValue(None)
