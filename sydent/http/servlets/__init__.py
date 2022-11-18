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

import copy
import functools
import json
import logging
from typing import Any, Awaitable, Callable, Dict, Iterable, TypeVar

from prometheus_client import Counter
from twisted.internet import defer
from twisted.web import server
from twisted.web.resource import Resource
from twisted.web.server import Request

from sydent.types import JsonDict
from sydent.util import json_decoder

logger = logging.getLogger(__name__)


request_counter = Counter(
    "sydent_http_received_requests",
    "Received requests",
    labelnames=("servlet", "method"),
)


class SydentResource(Resource):
    """A subclass of resource that tracks request metrics"""

    def __init__(self) -> None:
        self._name = self.__class__.__name__
        super().__init__()

    def render(self, request: Request) -> Any:
        request_counter.labels(self._name, request.method).inc()
        return super().render(request)


class MatrixRestError(Exception):
    """
    Handled by the jsonwrap wrapper. Any servlets that don't use this
    wrapper should catch this exception themselves.
    """

    def __init__(self, httpStatus: int, errcode: str, error: str):
        super(Exception, self).__init__(error)
        self.httpStatus = httpStatus
        self.errcode = errcode
        self.error = error


def get_args(
    request: Request, args: Iterable[str], required: bool = True
) -> Dict[str, Any]:
    """
    Helper function to get arguments for an HTTP request.
    Currently takes args from the top level keys of a json object or
    www-form-urlencoded for backwards compatibility on v1 endpoints only.

    ⚠️ BEWARE ⚠. If a v1 request provides its args in urlencoded form (either in
    a POST body or as URL query parameters), then we'll return `Dict[str, str]`.
    The caller may need to interpret these strings as e.g. an `int`, `bool`, etc.
    Arguments given as a json body are processed with `json.JSONDecoder.decode`,
    and so are automatically deserialised to a Python type. The caller should
    still validate that these have the correct type!

    :param request: The request received by the servlet.
    :param args: The args to look for in the request's parameters.
    :param required: Whether to raise a MatrixRestError with 400
        M_MISSING_PARAMS if an argument is not found.

    :raises: MatrixRestError if required is True and a given parameter
        was not found in the request's query parameters.
    :raises: MatrixRestError if we the request body contains bad JSON.
    :raises: MatrixRestError if arguments are given in www-form-urlencodedquery
        form, and some argument name or value is not a valid UTF-8-encoded
        string.

    :return: A dict containing the requested args and their values. String values
        are of type unicode.
    """
    assert request.path is not None
    v1_path = request.path.startswith(b"/_matrix/identity/api/v1")

    request_args = None
    # for v1 paths, only look for json args if content type is json
    if request.method in (b"POST", b"PUT") and (
        not v1_path
        or (
            request.requestHeaders.hasHeader("Content-Type")
            # type safety: getRawHeaders() will return a nonempty list because
            # the hasHeader call has returned True.
            and request.requestHeaders.getRawHeaders("Content-Type")[0].startswith(  # type: ignore[index]
                "application/json"
            )
        )
    ):
        try:
            # json.loads doesn't allow bytes in Python 3.5
            request_args = json_decoder.decode(request.content.read().decode("UTF-8"))
        except ValueError:
            raise MatrixRestError(400, "M_BAD_JSON", "Malformed JSON")

    # If we didn't get anything from that, and it's a v1 api path, try the request args
    # (element-web's usage of the ed25519 sign servlet currently involves
    # sending the params in the query string with a json body of 'null')
    if request_args is None and (v1_path or request.method == b"GET"):
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
                        "M_INVALID_PARAM",
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
            msg = "Missing parameters: " + (",".join(missing))
            raise MatrixRestError(400, "M_MISSING_PARAMS", msg)

    return request_args


Res = TypeVar("Res", bound=Resource)


def jsonwrap(f: Callable[[Res, Request], JsonDict]) -> Callable[[Res, Request], bytes]:
    @functools.wraps(f)
    def inner(self: Res, request: Request) -> bytes:

        """
        Runs a web handler function with the given request and parameters, then
        converts its result into JSON and returns it. If an error happens, also sets
        the HTTP response code.

        :param self: The current object.
        :param request: The request to process.

        :return: The JSON payload to send as a response to the request.
        """
        try:
            request.setHeader("Content-Type", "application/json")
            return dict_to_json_bytes(f(self, request))
        except MatrixRestError as e:
            request.setResponseCode(e.httpStatus)
            return dict_to_json_bytes({"errcode": e.errcode, "error": e.error})
        except Exception:
            logger.exception("Exception processing request")
            request.setHeader("Content-Type", "application/json")
            request.setResponseCode(500)
            return dict_to_json_bytes(
                {
                    "errcode": "M_UNKNOWN",
                    "error": "Internal Server Error",
                }
            )

    return inner


AsyncRenderer = Callable[[Res, Request], Awaitable[JsonDict]]


def asyncjsonwrap(f: AsyncRenderer[Res]) -> Callable[[Res, Request], object]:
    async def render(f: AsyncRenderer[Res], self: Res, request: Request) -> None:
        request.setHeader("Content-Type", "application/json")
        try:
            result = await f(self, request)
            request.write(dict_to_json_bytes(result))
        except MatrixRestError as e:
            request.setResponseCode(e.httpStatus)
            request.write(dict_to_json_bytes({"errcode": e.errcode, "error": e.error}))
        except Exception:
            logger.exception("Request processing failed")
            request.setResponseCode(500)
            request.write(
                dict_to_json_bytes(
                    {"errcode": "M_UNKNOWN", "error": "Internal Server Error"}
                )
            )
        request.finish()

    @functools.wraps(f)
    def inner(self: Res, request: Request) -> object:
        """
        Runs an asynchronous web handler function with the given arguments.

        :param self: The servelet instance
        :param request: The request that `f` will serve.

        :return: An opaque object to tell the servlet that the response isn't ready yet
            and will come later.
        """
        defer.ensureDeferred(render(f, self, request))
        return server.NOT_DONE_YET

    return inner


def send_cors(request: Request) -> None:
    request.setHeader("Access-Control-Allow-Origin", "*")
    request.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
    request.setHeader("Access-Control-Allow-Headers", "*")


def dict_to_json_bytes(content: JsonDict) -> bytes:
    """
    Converts a dict into JSON and encodes it to bytes.

    :return: The JSON bytes.
    """
    return json.dumps(content).encode("UTF-8")
