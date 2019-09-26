# -*- coding: utf-8 -*-

# Copyright 2014 OpenMarket Ltd
# Copyright 2019 The Matrix.org Foundation C.I.C.
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

import json
import logging

from twisted.web.resource import Resource
from twisted.internet import defer
from twisted.web import server

from sydent.http.httpclient import SimpleHttpClient
from sydent.db.valsession import ThreePidValSessionStore
from sydent.http.servlets import get_args, jsonwrap, send_cors, MatrixRestError
from sydent.http.auth import authIfV2
from sydent.validators import SessionExpiredException, IncorrectClientSecretException, InvalidSessionIdException,\
    SessionNotValidatedException


logger = logging.getLogger(__name__)


def isMxidDomainAllowed(domain):
    if ':' in domain:
        domain = domain.split(':', 1)[0]
    return domain == 'matrix.org' or domain.endswith('.modular.im')

class ThreePidBindServlet(Resource):
    def __init__(self, sydent):
        self.sydent = sydent

    def render_POST(self, request):
        self._async_render_POST(request)
        return server.NOT_DONE_YET

    @defer.inlineCallbacks
    def _async_render_POST(self, request):
        send_cors(request)

        account = authIfV2(self.sydent, request)

        isV2 = request.path.startswith('/_matrix/identity/v2')

        args = get_args(request, ('sid', 'client_secret', 'mxid'))

        sid = args['sid']
        mxid = args['mxid']
        clientSecret = args['client_secret']

        # let's say an mxid must be at least 3 chars (@, : and nonempty domain)
        if len(mxid) < 3 or mxid[0] != '@':
            request.write(json.dumps({
                'errcode': 'M_INVALID_PARAM',
                'error': "Invalid mxid",
            }))
            request.finish()
            defer.returnValue(None)
        parts = mxid[1:].split(':', 1)
        if len(parts) != 2:
            request.write(json.dumps({
                'errcode': 'M_INVALID_PARAM',
                'error': "Invalid mxid",
            }))
            request.finish()
            defer.returnValue(None)
        mxid_localpart, mxid_domain = parts

        # Return the same error for not found / bad client secret otherwise people can get information about
        # sessions without knowing the secret
        noMatchError = {'errcode': 'M_NO_VALID_SESSION',
                        'error': "No valid session was found matching that sid and client secret"}

        if account:
            # This is a v2 API so only allow binding to the logged in user id
            if account.userId != mxid:
                raise MatrixRestError(403, 'M_UNAUTHORIZED', "This user is prohibited from binding to the mxid");

        try:
            valSessionStore = ThreePidValSessionStore(self.sydent)
            s = valSessionStore.getValidatedSession(sid, clientSecret)
        except IncorrectClientSecretException:
            request.write(json.dumps(noMatchError))
            request.finish()
            defer.returnValue(None)
        except SessionExpiredException:
            request.write(json.dumps({'errcode': 'M_SESSION_EXPIRED',
                    'error': "This validation session has expired: call requestToken again"}))
            request.finish()
            defer.returnValue(None)
        except InvalidSessionIdException:
            request.write(json.dumps(noMatchError))
            request.finish()
            defer.returnValue(None)
        except SessionNotValidatedException:
            request.write(json.dumps({'errcode': 'M_SESSION_NOT_VALIDATED',
                    'error': "This validation session has not yet been completed"}))
            request.finish()
            defer.returnValue(None)

        # check HS of mxid and only accept bindings to a set of whitelisted HSes
        allow_mxid_domain = False

        if isV2:
            logger.info("Allowing any domain because path is v2")
            allow_mxid_domain = True
        elif isMxidDomainAllowed(mxid_domain):
            logger.info("Allowing domain %s" % (mxid_domain,))
            allow_mxid_domain = True
        else:
            # do the same check on the .well-known lookup
            httpClient = SimpleHttpClient(self.sydent)
            try:
                wellKnown = yield httpClient.get_json("https://%s/.well-known/matrix/server" % (mxid_domain,))
                if 'm.server' in wellKnown:
                    if isMxidDomainAllowed(wellKnown['m.server']):
                        logger.info("Allowing domain %s due to .well-known: %s" % (mxid_domain, wellKnown['m.server']))
                        allow_mxid_domain = True
                    else:
                        logger.info("Not allowing domain %s from to .well-known: %s" % (mxid_domain, wellKnown['m.server']))
            except Exception as e:
                # we could be more specific with our errors but we're not going to allow it in any case
                logger.info(".well-known lookup failed for %s: %r" % (mxid_domain, e))
                pass

        if allow_mxid_domain:
            res = self.sydent.threepidBinder.addBinding(s.medium, s.address, mxid)
            request.write(json.dumps(res))
        else:
            # ignore and return fake response, otherwise synapse gets confused
            request.write(json.dumps({
                'medium': s.medium,
                'address': s.address,
                'mxid': mxid,
            }))

        request.finish()

    def render_OPTIONS(self, request):
        send_cors(request)
        request.setResponseCode(200)
        return b''
