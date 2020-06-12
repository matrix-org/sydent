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

from signedjson.sign import SignatureVerifyException
import json
import logging
from sydent.http.servlets import deferjsonwrap
from sydent.db.profiles import ProfileStore


logger = logging.getLogger(__name__)

MAX_BATCH_SIZE = 200


class ProfileReplicationServlet(Resource):
    isLeaf = True

    def __init__(self, syd):
        self.sydent = syd

    def render_POST(self, request):
        self._async_render_POST(request)
        return server.NOT_DONE_YET

    @deferjsonwrap
    @defer.inlineCallbacks
    def _async_render_POST(self, request):
        yield
        try:
            content = request.content.read()
            if isinstance(content, bytes):
                content = content.decode("UTF-8")

            body = json.loads(content)
        except ValueError:
            request.setResponseCode(400)
            return {'errcode': 'M_BAD_JSON', 'error': 'Malformed JSON'}

        missing = [k for k in ("batchnum", "batch", "origin_server") if k not in body]
        if len(missing) > 0:
            request.setResponseCode(400)
            msg = "Missing parameters: "+(",".join(missing))
            return {'errcode': 'M_MISSING_PARAMS', 'error': msg}

        try:
            yield self.sydent.sig_verifier.verifyServerSignedJson(body, self.sydent.user_dir_allowed_hses)
        except SignatureVerifyException:
            request.setResponseCode(403)
            msg = "Signature verification failed or origin not whitelisted"
            return {'errcode': 'M_FORBIDDEN', 'error': msg}

        batchnum = body["batchnum"]
        batch = body["batch"]
        origin_server = body["origin_server"]

        profile_store = ProfileStore(self.sydent)

        latest_batch_on_host = profile_store.getLastBatchForOriginServer(origin_server)
        if latest_batch_on_host is None:
            latest_batch_on_host = -1
        if batchnum <= latest_batch_on_host:
            logger.info("Ignoring batch %d from %s: we already have %d", batchnum, origin_server, latest_batch_on_host)
            # we already have this batch, thanks
            return {}
        else:
            # good, this is the next batch
            if len(batch) > MAX_BATCH_SIZE:
                logger.warn("Host %s sent batch of %s which exceeds max of %d", origin_server, len(batch), MAX_BATCH_SIZE)
                request.setResponseCode(400)
                return {'errcode': 'M_UNKNOWN', 'error': 'batch size exceeds max of %d' % (MAX_BATCH_SIZE,)}
                
            bad_uids = []
            for uid, info in batch.items():
                if info is not None and ('display_name' not in info or 'avatar_url' not in info):
                    bad_uids.append(uid)
            if len(bad_uids) > 0:
                logger.warn("Host %s sent batch with missing fields", origin_server)
                request.setResponseCode(400)
                msg = "Missing data for user IDs: %s (required: display_name, avatar_url" % (','.join(bad_uids,))
                return {'errcode': 'M_UNKNOWN', 'error': msg}

            logger.info("Storing %d profiles in batch %d from %s", len(batch), batchnum, origin_server)
            profile_store.addBatch(origin_server, batchnum, batch)
            return {}
