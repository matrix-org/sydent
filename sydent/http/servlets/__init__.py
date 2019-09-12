# -*- coding: utf-8 -*-

# Copyright 2014 OpenMarket Ltd
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
import json
import copy
import functools

from twisted.internet import defer
from twisted.web import server


logger = logging.getLogger(__name__)


class MatrixRestError(Exception):
    """
    Handled by the jsonwrap wrapper. Any servlets that don't use this
    wrapper should catch this exception themselves.
    """
    def __init__(self, httpStatus, errcode, error):
        super(Exception, self).__init__(error)
        self.httpStatus = httpStatus
        self.errcode = errcode
        self.error = error


def get_args(request, required_args):
    """
    Helper function to get arguments for an HTTP request.
    Currently takes args from the top level keys of a json object or
    www-form-urlencoded for backwards compatability on v1 endpoints only.
    Returns a tuple (error, args) where if error is non-null,
    the request is malformed. Otherwise, args contains the
    parameters passed.
    """
    v1_path = request.path.startswith('/_matrix/identity/api/v1')

    args = None
    # for v1 paths, only look for json args if content type is json
    if (
        request.method in ('POST', 'PUT') and (
            not v1_path or (
                request.requestHeaders.hasHeader('Content-Type') and
                request.requestHeaders.getRawHeaders('Content-Type')[0].startswith('application/json')
            )
        )
    ):
        try:
            args = json.load(request.content)
        except ValueError:
            raise MatrixRestError(400, 'M_BAD_JSON', 'Malformed JSON')

    # If we didn't get anything from that, and it's a v1 api path, try the request args
    # (riot-web's usage of the ed25519 sign servlet currently involves
    # sending the params in the query string with a json body of 'null')
    if args is None and (v1_path or request.method == 'GET'):
        args = copy.copy(request.args)
        # Twisted supplies everything as an array because it's valid to
        # supply the same params multiple times with www-form-urlencoded
        # params. This make it incompatible with the json object though,
        # so we need to convert one of them. Since this is the
        # backwards-compat option, we convert this one.
        for k, v in args.items():
            if isinstance(v, list) and len(v) == 1:
                args[k] = v[0]
    elif args is None:
        args = {}

    missing = []
    for a in required_args:
        if a not in args:
            missing.append(a)

    if len(missing) > 0:
        request.setResponseCode(400)
        msg = "Missing parameters: "+(",".join(missing))
        raise MatrixRestError(400, 'M_MISSING_PARAMS', msg)

    return args

def jsonwrap(f):
    @functools.wraps(f)
    def inner(self, request, *args, **kwargs):
        try:
            request.setHeader("Content-Type", "application/json")
            return json.dumps(f(self, request, *args, **kwargs)).encode("UTF-8")
        except MatrixRestError as e:
            request.setResponseCode(e.httpStatus)
            return json.dumps({
                "errcode": e.errcode,
                "error": e.error,
            })
        except Exception:
            logger.exception("Exception processing request");
            request.setHeader("Content-Type", "application/json")
            request.setResponseCode(500)
            return json.dumps({
                "errcode": "M_UNKNOWN",
                "error": "Internal Server Error",
            })
    return inner

def deferjsonwrap(f):
    def reqDone(resp, request):
        request.setHeader("Content-Type", "application/json")
        request.setResponseCode(200)
        request.write(json.dumps(resp).encode("UTF-8"))
        request.finish()

    def reqErr(failure, request):
        request.setHeader("Content-Type", "application/json")
        if failure.check(MatrixRestError) is not None:
            request.setResponseCode(failure.value.httpStatus)
            request.write(json.dumps({'errcode': failure.value.errcode, 'error': failure.value.error}))
        else:
            logger.error("Request processing failed: %r, %s", failure, failure.getTraceback())
            request.setResponseCode(500)
            request.write(json.dumps({'errcode': 'M_UNKNOWN', 'error': 'Internal Server Error'}))
        request.finish()

    def inner(*args, **kwargs):
        request = args[1]

        d = defer.maybeDeferred(f, *args, **kwargs)
        d.addCallback(reqDone, request)
        d.addErrback(reqErr, request)
        return server.NOT_DONE_YET
    return inner

def send_cors(request):
    request.setHeader("Access-Control-Allow-Origin", "*")
    request.setHeader("Access-Control-Allow-Methods",
                      "GET, POST, PUT, DELETE, OPTIONS")
    request.setHeader("Access-Control-Allow-Headers", "*")
