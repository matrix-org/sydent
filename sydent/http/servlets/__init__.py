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


def get_args(request, args, required=True):
    """
    Helper function to get arguments for an HTTP request.
    Currently takes args from the top level keys of a json object or
    www-form-urlencoded for backwards compatibility on v1 endpoints only.
    Returns a tuple (error, args) where if error is non-null,
    the request is malformed. Otherwise, args contains the
    parameters passed.

    :param request: The request received by the servlet.
    :type request: twisted.web.server.Request
    :param args: The args to look for in the request's parameters.
    :type args: tuple[unicode]
    :param required: Whether to raise a MatrixRestError with 400
        M_MISSING_PARAMS if an argument is not found.
    :type required: bool

    :raises: MatrixRestError if required is True and a given parameter
        was not found in the request's query parameters.

    :return: A dict containing the requested args and their values. String values
        are of type unicode.
    :rtype: dict[unicode, any]
    """
    v1_path = request.path.startswith(b'/_matrix/identity/api/v1')

    request_args = None
    # for v1 paths, only look for json args if content type is json
    if (
        request.method in (b'POST', b'PUT') and (
            not v1_path or (
                request.requestHeaders.hasHeader('Content-Type') and
                request.requestHeaders.getRawHeaders('Content-Type')[0].startswith('application/json')
            )
        )
    ):
        try:
            # json.loads doesn't allow bytes in Python 3.5
            request_args = json.loads(request.content.read().decode("UTF-8"))
        except ValueError:
            raise MatrixRestError(400, 'M_BAD_JSON', 'Malformed JSON')

    # If we didn't get anything from that, and it's a v1 api path, try the request args
    # (element-web's usage of the ed25519 sign servlet currently involves
    # sending the params in the query string with a json body of 'null')
    if request_args is None and (v1_path or request.method == b'GET'):
        request_args_bytes = copy.copy(request.args)
        # Twisted supplies everything as an array because it's valid to
        # supply the same params multiple times with www-form-urlencoded
        # params. This make it incompatible with the json object though,
        # so we need to convert one of them. Since this is the
        # backwards-compat option, we convert this one.
        request_args = {}
        for k, v in request_args_bytes.items():
            if isinstance(v, list) and len(v) == 1:
                try:
                    request_args[k.decode("UTF-8")] = v[0].decode("UTF-8")
                except UnicodeDecodeError:
                    # Get a version of the key that has non-UTF-8 characters replaced by
                    # their \xNN escape sequence so it doesn't raise another exception.
                    safe_k = k.decode("UTF-8", errors="backslashreplace")
                    raise MatrixRestError(
                        400,
                        'M_INVALID_PARAM',
                        "Parameter %s and its value must be valid UTF-8" % safe_k,
                    )

    elif request_args is None:
        request_args = {}

    if required:
        # Check for any missing arguments
        missing = []
        for a in args:
            if a not in request_args:
                missing.append(a)

        if len(missing) > 0:
            request.setResponseCode(400)
            msg = "Missing parameters: "+(",".join(missing))
            raise MatrixRestError(400, 'M_MISSING_PARAMS', msg)

    return request_args


def jsonwrap(f):
    @functools.wraps(f)
    def inner(self, request, *args, **kwargs):
        """
        Runs a web handler function with the given request and parameters, then
        converts its result into JSON and returns it. If an error happens, also sets
        the HTTP response code.

        :param self: The current object.
        :param request: The request to process.
        :type request: twisted.web.server.Request
        :param args: The arguments to pass to the function.
        :param kwargs: The keyword arguments to pass to the function.

        :return: The JSON payload to send as a response to the request.
        :rtype bytes
        """
        try:
            request.setHeader("Content-Type", "application/json")
            return dict_to_json_bytes(f(self, request, *args, **kwargs))
        except MatrixRestError as e:
            request.setResponseCode(e.httpStatus)
            return dict_to_json_bytes({"errcode": e.errcode, "error": e.error})
        except Exception:
            logger.exception("Exception processing request")
            request.setHeader("Content-Type", "application/json")
            request.setResponseCode(500)
            return dict_to_json_bytes({
                "errcode": "M_UNKNOWN",
                "error": "Internal Server Error",
            })
    return inner


def deferjsonwrap(f):
    def reqDone(resp, request):
        """
        Converts the given response content into JSON and encodes it to bytes, then
        writes it as the response to the given request with the right headers.

        :param resp: The response content to convert to JSON and encode.
        :type resp: dict[str, any]
        :param request: The request to respond to.
        :type request: twisted.web.server.Request
        """
        request.setHeader("Content-Type", "application/json")
        request.write(dict_to_json_bytes(resp))
        request.finish()

    def reqErr(failure, request):
        """
        Logs the given failure. If the failure is a MatrixRestError, writes a response
        using the info it contains, otherwise responds with 500 Internal Server Error.

        :param failure: The failure to process.
        :type failure: twisted.python.failure.Failure
        :param request: The request to respond to.
        :type request: twisted.web.server.Request
        """
        request.setHeader("Content-Type", "application/json")
        if failure.check(MatrixRestError) is not None:
            request.setResponseCode(failure.value.httpStatus)
            request.write(dict_to_json_bytes({'errcode': failure.value.errcode, 'error': failure.value.error}))
        else:
            logger.error("Request processing failed: %r, %s", failure, failure.getTraceback())
            request.setResponseCode(500)
            request.write(dict_to_json_bytes({'errcode': 'M_UNKNOWN', 'error': 'Internal Server Error'}))
        request.finish()

    def inner(*args, **kwargs):
        """
        Runs an asynchronous web handler function with the given arguments and add
        reqDone and reqErr as the resulting Deferred's callbacks.

        :param args: The arguments to pass to the function.
        :param kwargs: The keyword arguments to pass to the function.

        :return: A special code to tell the servlet that the response isn't ready yet
            and will come later.
        :rtype: int
        """
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


def dict_to_json_bytes(content):
    """
    Converts a dict into JSON and encodes it to bytes.

    :param content:
    :type content: dict[any, any]

    :return: The JSON bytes.
    :rtype: bytes
    """
    return json.dumps(content).encode("UTF-8")
