# -*- coding: utf-8 -*-

# Copyright 2014 OpenMarket Ltd
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

import json
import logging

from sydent.http.servlets import get_args, jsonwrap
from sydent.hs_federation.verifier import NoAuthenticationError
from signedjson.sign import SignatureVerifyException
from sydent.db.valsession import ThreePidValSessionStore
from sydent.validators import SessionExpiredException, IncorrectClientSecretException, InvalidSessionIdException,\
    SessionNotValidatedException

from twisted.web.resource import Resource
from twisted.web import server
from twisted.internet import defer

logger = logging.getLogger(__name__)

class ThreePidUnbindServlet(Resource):
    def __init__(self, sydent):
        self.sydent = sydent

    def render_POST(self, request):
        self._async_render_POST(request)
        return server.NOT_DONE_YET

    @defer.inlineCallbacks
    def _async_render_POST(self, request):
        try:
            try:
                body = json.load(request.content)
            except ValueError:
                request.setResponseCode(400)
                request.write(json.dumps({'errcode': 'M_BAD_JSON', 'error': 'Malformed JSON'}))
                request.finish()
                return

            missing = [k for k in ("threepid", "mxid") if k not in body]
            if len(missing) > 0:
                request.setResponseCode(400)
                msg = "Missing parameters: "+(",".join(missing))
                request.write(json.dumps({'errcode': 'M_MISSING_PARAMS', 'error': msg}))
                request.finish()
                return

            threepid = body['threepid']
            mxid = body['mxid']

            if 'medium' not in threepid or 'address' not in threepid:
                request.setResponseCode(400)
                request.write(json.dumps({'errcode': 'M_MISSING_PARAMS', 'error': 'Threepid lacks medium / address'}))
                request.finish()
                return

            # We now check for authentication in two different ways, depending
            # on the contents of the request. If the user has supplied "sid"
            # (the Session ID returned by Sydent during the original binding)
            # and "client_secret" fields, they are trying to prove that they
            # were the original author of the bind. We then check that what
            # they supply matches and if it does, allow the unbind.
            # 
            # However if these fields are not supplied, we instead check
            # whether the request originated from a homeserver, and if so the
            # same homeserver that originally created the bind. We do this by
            # checking the signature of the request. If it all matches up, we
            # allow the unbind.
            #
            # Only one method of authentication is required.
            if 'sid' in body and 'client_secret' in body:
                sid = body['sid']
                client_secret = body['client_secret']

                valSessionStore = ThreePidValSessionStore(self.sydent)

                noMatchError = {'errcode': 'M_NO_VALID_SESSION',
                                'error': "No valid session was found matching that sid and client secret"}

                try:
                    s = valSessionStore.getValidatedSession(sid, client_secret)
                except IncorrectClientSecretException:
                    request.setResponseCode(401)
                    request.write(json.dumps(noMatchError))
                    request.finish()
                    return
                except InvalidSessionIdException:
                    request.setResponseCode(401)
                    request.write(json.dumps(noMatchError))
                    request.finish()
                    return
                except SessionNotValidatedException:
                    request.setResponseCode(403)
                    request.write(json.dumps({
                        'errcode': 'M_SESSION_NOT_VALIDATED',
                        'error': "This validation session has not yet been completed"
                    }))
                    return
                
                if s.medium != threepid['medium'] or s.address != threepid['address']:
                    request.setResponseCode(403)
                    request.write(json.dumps({
                        'errcode': 'M_FORBIDDEN',
                        'error': 'Provided session information does not match medium/address combo',
                    }))
                    request.finish()
                    return
            else:
                try:
                    origin_server_name = yield self.sydent.sig_verifier.authenticate_request(request, body)
                except SignatureVerifyException as ex:
                    request.setResponseCode(401)
                    request.write(json.dumps({'errcode': 'M_FORBIDDEN', 'error': ex.message}))
                    request.finish()
                    return
                except NoAuthenticationError as ex:
                    request.setResponseCode(401)
                    request.write(json.dumps({'errcode': 'M_FORBIDDEN', 'error': ex.message}))
                    request.finish()
                    return
                except:
                    logger.exception("Exception whilst authenticating unbind request")
                    request.setResponseCode(500)
                    request.write(json.dumps({'errcode': 'M_UNKNOWN', 'error': 'Internal Server Error'}))
                    request.finish()
                    return

                if not mxid.endswith(':' + origin_server_name):
                    request.setResponseCode(403)
                    request.write(json.dumps({'errcode': 'M_FORBIDDEN', 'error': 'Origin server name does not match mxid'}))
                    request.finish()
                    return

            res = self.sydent.threepidBinder.removeBinding(threepid, mxid)

            request.write(json.dumps({}))
            request.finish()
        except Exception as ex:
            logger.exception("Exception whilst handling unbind")
            request.setResponseCode(500)
            request.write(json.dumps({'errcode': 'M_UNKNOWN', 'error': ex.message}))
            request.finish()
