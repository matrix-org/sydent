# -*- coding: utf-8 -*-
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

import logging
import re

import ConfigParser
from inspect import getcallargs

from twisted.internet import defer, reactor

from sydent.sydent import CONFIG_DEFAULTS, Sydent
from tests.logcontext import LoggingContext

logger = logging.getLogger(__name__)


def default_config(name):
    """
    Create a reasonable test config.
    """
    config_dict = CONFIG_DEFAULTS

    config_dict['general']['name'] = name
    config_dict['general']['log.path'] = 'sydent.log'
    config_dict['crypto']['signing_key'] = 'ed25519 a_lPym qvioDNmfExFBRPgdTU+wtFYKq4JfwFRv7sYVgWvmgJg'
    config_dict['db']['db.file'] = ':memory:'

    cfg = ConfigParser.SafeConfigParser()

    for sect, entries in config_dict.items():
        cfg.add_section(sect)
        for k, v in entries.items():
            cfg.set(sect, k, v)

    return cfg


def setup_test_identity_server(
    name="test",
    config=None,
    reactor=None,
    **kargs
):
    if config is None:
        config = default_config(name)

    ident_server = Sydent(cfg=config, reactor=reactor, **kargs)

    return ident_server


def get_mock_call_args(pattern_func, mock_func):
    """ Return the arguments the mock function was called with interpreted
    by the pattern functions argument list.
    """
    invoked_args, invoked_kargs = mock_func.call_args
    return getcallargs(pattern_func, *invoked_args, **invoked_kargs)


def mock_getRawHeaders(headers=None):
    headers = headers if headers is not None else {}

    def getRawHeaders(name, default=None):
        return headers.get(name, default)

    return getRawHeaders

class MockKey(object):
    alg = "mock_alg"
    version = "mock_version"
    signature = b"\x9a\x87$"

    @property
    def verify_key(self):
        return self

    def sign(self, message):
        return self

    def verify(self, message, sig):
        assert sig == b"\x9a\x87$"

    def encode(self):
        return b"<fake_encoded_key>"


class MockClock(object):
    now = 1000

    def __init__(self):
        # list of lists of [absolute_time, callback, expired] in no particular
        # order
        self.timers = []
        self.loopers = []

    def time(self):
        return self.now

    def time_msec(self):
        return self.time() * 1000

    def call_later(self, delay, callback, *args, **kwargs):
        current_context = LoggingContext.current_context()

        def wrapped_callback():
            LoggingContext.thread_local.current_context = current_context
            callback(*args, **kwargs)

        t = [self.now + delay, wrapped_callback, False]
        self.timers.append(t)

        return t

    def looping_call(self, function, interval):
        self.loopers.append([function, interval / 1000.0, self.now])

    def cancel_call_later(self, timer, ignore_errs=False):
        if timer[2]:
            if not ignore_errs:
                raise Exception("Cannot cancel an expired timer")

        timer[2] = True
        self.timers = [t for t in self.timers if t != timer]

    # For unit testing
    def advance_time(self, secs):
        self.now += secs

        timers = self.timers
        self.timers = []

        for t in timers:
            time, callback, expired = t

            if expired:
                raise Exception("Timer already expired")

            if self.now >= time:
                t[2] = True
                callback()
            else:
                self.timers.append(t)

        for looped in self.loopers:
            func, interval, last = looped
            if last + interval < self.now:
                func()
                looped[2] = self.now

    def advance_time_msec(self, ms):
        self.advance_time(ms / 1000.0)

    def time_bound_deferred(self, d, *args, **kwargs):
        # We don't bother timing things out for now.
        return d


def _format_call(args, kwargs):
    return ", ".join(
        ["%r" % (a) for a in args] + ["%s=%r" % (k, v) for k, v in kwargs.items()]
    )


class DeferredMockCallable(object):
    """A callable instance that stores a set of pending call expectations and
    return values for them. It allows a unit test to assert that the given set
    of function calls are eventually made, by awaiting on them to be called.
    """

    def __init__(self):
        self.expectations = []
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))

        if not self.expectations:
            raise ValueError(
                "%r has no pending calls to handle call(%s)"
                % (self, _format_call(args, kwargs))
            )

        for (call, result, d) in self.expectations:
            if args == call[1] and kwargs == call[2]:
                d.callback(None)
                return result

        failure = AssertionError(
            "Was not expecting call(%s)" % (_format_call(args, kwargs))
        )

        for _, _, d in self.expectations:
            try:
                d.errback(failure)
            except Exception:
                pass

        raise failure

    def expect_call_and_return(self, call, result):
        self.expectations.append((call, result, defer.Deferred()))

    @defer.inlineCallbacks
    def await_calls(self, timeout=1000):
        deferred = defer.DeferredList(
            [d for _, _, d in self.expectations], fireOnOneErrback=True
        )

        timer = reactor.callLater(
            timeout / 1000,
            deferred.errback,
            AssertionError(
                "%d pending calls left: %s"
                % (
                    len([e for e in self.expectations if not e[2].called]),
                    [e for e in self.expectations if not e[2].called],
                )
            ),
        )

        yield deferred

        timer.cancel()

        self.calls = []

    def assert_had_no_calls(self):
        if self.calls:
            calls = self.calls
            self.calls = []

            raise AssertionError(
                "Expected not to received any calls, got:\n"
                + "\n".join(["call(%s)" % _format_call(c[0], c[1]) for c in calls])
            )


_hexdig = '0123456789ABCDEFabcdef'
_hextobyte = None


def unquote_to_bytes(string):
    """unquote_to_bytes('abc%20def') -> b'abc def'."""
    # Note: strings are encoded as UTF-8. This is only an issue if it contains
    # unescaped non-ASCII characters, which URIs should not.
    if not string:
        # Is it a string-like object?
        string.split
        return b''
    if isinstance(string, str):
        string = string.encode('utf-8')
    bits = string.split(b'%')
    if len(bits) == 1:
        return string
    res = [bits[0]]
    append = res.append
    # Delay the initialization of the table to not waste memory
    # if the function is never called
    global _hextobyte
    if _hextobyte is None:
        _hextobyte = {(a + b).encode(): bytes.fromhex(a + b)
                      for a in _hexdig for b in _hexdig}
    for item in bits[1:]:
        try:
            append(_hextobyte[item[:2]])
            append(item[2:])
        except KeyError:
            append(b'%')
            append(item)
    return b''.join(res)


_asciire = re.compile('([\x00-\x7f]+)')

def unquote(string, encoding='utf-8', errors='replace'):
    """Replace %xx escapes by their single-character equivalent. The optional
    encoding and errors parameters specify how to decode percent-encoded
    sequences into Unicode characters, as accepted by the bytes.decode()
    method.
    By default, percent-encoded sequences are decoded with UTF-8, and invalid
    sequences are replaced by a placeholder character.

    unquote('abc%20def') -> 'abc def'.
    """
    if '%' not in string:
        string.split
        return string
    if encoding is None:
        encoding = 'utf-8'
    if errors is None:
        errors = 'replace'
    bits = _asciire.split(string)
    res = [bits[0]]
    append = res.append
    for i in range(1, len(bits), 2):
        append(unquote_to_bytes(bits[i]).decode(encoding, errors))
        append(bits[i + 1])
    return ''.join(res)
