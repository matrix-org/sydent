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

import gc
import logging

from canonicaljson import json

import twisted
import twisted.logger
from twisted.internet.defer import Deferred
from twisted.trial import unittest
from twisted.web.server import Request
from twisted.web.resource import Resource

from tests.logcontext import LoggingContext
from tests.server import make_request, render, setup_test_identity_server, ThreadedMemoryReactorClock
from tests.test_utils.logging_setup import setup_logging
from tests.utils import default_config

from sydent.sydent import Sydent

setup_logging()


def around(target):
    """A CLOS-style 'around' modifier, which wraps the original method of the
    given instance with another piece of code.

    @around(self)
    def method_name(orig, *args, **kwargs):
        return orig(*args, **kwargs)
    """

    def _around(code):
        name = code.__name__
        orig = getattr(target, name)

        def new(*args, **kwargs):
            return code(orig, *args, **kwargs)

        setattr(target, name, new)

    return _around


class TestCase(unittest.TestCase):
    """A subclass of twisted.trial's TestCase which looks for 'loglevel'
    attributes on both itself and its individual test methods, to override the
    root logger's logging level while that test (case|method) runs."""

    def __init__(self, methodName, *args, **kwargs):
        super(TestCase, self).__init__(methodName, *args, **kwargs)

        method = getattr(self, methodName)

        level = getattr(method, "loglevel", getattr(self, "loglevel", None))

        @around(self)
        def setUp(orig):
            # enable debugging of delayed calls - this means that we get a
            # traceback when a unit test exits leaving things on the reactor.
            twisted.internet.base.DelayedCall.debug = True

            # if we're not starting in the sentinel logcontext, then to be honest
            # all future bets are off.
            if LoggingContext.current_context() is not LoggingContext.sentinel:
                self.fail(
                    "Test starting with non-sentinel logging context %s"
                    % (LoggingContext.current_context(),)
                )

            old_level = logging.getLogger().level
            if level is not None and old_level != level:

                @around(self)
                def tearDown(orig):
                    ret = orig()
                    logging.getLogger().setLevel(old_level)
                    return ret

                logging.getLogger().setLevel(level)

            return orig()

        @around(self)
        def tearDown(orig):
            ret = orig()
            # force a GC to workaround problems with deferreds leaking logcontexts when
            # they are GCed (see the logcontext docs)
            gc.collect()
            LoggingContext.set_current_context(LoggingContext.sentinel)

            return ret

    def assertObjectHasAttributes(self, attrs, obj):
        """Asserts that the given object has each of the attributes given, and
        that the value of each matches according to assertEquals."""
        for (key, value) in attrs.items():
            if not hasattr(obj, key):
                raise AssertionError("Expected obj to have a '.%s'" % key)
            try:
                self.assertEquals(attrs[key], getattr(obj, key))
            except AssertionError as e:
                raise (type(e))(e.message + " for '.%s'" % key)

    def assert_dict(self, required, actual):
        """Does a partial assert of a dict.

        Args:
            required (dict): The keys and value which MUST be in 'actual'.
            actual (dict): The test result. Extra keys will not be checked.
        """
        for key in required:
            self.assertEquals(
                required[key], actual[key], msg="%s mismatch. %s" % (key, actual)
            )


def DEBUG(target):
    """A decorator to set the .loglevel attribute to logging.DEBUG.
    Can apply to either a TestCase or an individual test method."""
    target.loglevel = logging.DEBUG
    return target


def INFO(target):
    """A decorator to set the .loglevel attribute to logging.INFO.
    Can apply to either a TestCase or an individual test method."""
    target.loglevel = logging.INFO
    return target


class IdentityServerTestCase(TestCase):
    """
    A base TestCase that reduces boilerplate for HomeServer-using test cases.
    """

    def setUp(self):
        """
        Set up the TestCase by calling the homeserver constructor, optionally
        hijacking the authentication system to return a fixed user, and then
        calling the prepare function.
        """
        self.reactor = ThreadedMemoryReactorClock()
        self.resource = Resource()

        self.ident_server = self.make_identity_server()

        if self.ident_server is None:
            raise Exception("No identity server returned from make_identity_server.")

        if not isinstance(self.ident_server, Sydent):
            raise Exception("An identity server wasn't returned, but %r" % (self.ident_server,))

    def make_identity_server(self):
        """
        Make and return a homeserver.

        Args:
            reactor: A Twisted Reactor, or something that pretends to be one.
            clock (synapse.util.Clock): The Clock, associated with the reactor.

        Returns:
            A homeserver (synapse.server.HomeServer) suitable for testing.

        Function to be overridden in subclasses.
        """
        ident_server = self.setup_test_identity_server()
        return ident_server

    def default_config(self, name="test"):
        """
        Get a default HomeServer config dict.

        Args:
            name (str): The homeserver name/domain.
        """
        return default_config(name)

    def prepare(self, reactor, clock, homeserver):
        """
        Prepare for the test.  This involves things like mocking out parts of
        the homeserver, or building test data common across the whole test
        suite.

        Args:
            reactor: A Twisted Reactor, or something that pretends to be one.
            clock (synapse.util.Clock): The Clock, associated with the reactor.
            homeserver (synapse.server.HomeServer): The HomeServer to test
            against.

        Function to optionally be overridden in subclasses.
        """
    def make_request(
        self,
        method,
        path,
        content=b"",
        access_token=None,
        request=Request,
        shorthand=True,
        federation_auth_origin=None,
    ):
        """
        Create a SynapseRequest at the path using the method and containing the
        given content.

        Args:
            method (bytes/unicode): The HTTP request method ("verb").
            path (bytes/unicode): The HTTP path, suitably URL encoded (e.g.
            escaped UTF-8 & spaces and such).
            content (bytes or dict): The body of the request. JSON-encoded, if
            a dict.
            shorthand: Whether to try and be helpful and prefix the given URL
            with the usual REST API path, if it doesn't contain it.
            federation_auth_origin (bytes|None): if set to not-None, we will add a fake
                Authorization header pretenting to be the given server name.

        Returns:
            Tuple[synapse.http.site.SynapseRequest, channel]
        """
        if isinstance(content, dict):
            content = json.dumps(content).encode("utf8")

        return make_request(
            self.reactor,
            method,
            path,
            content,
            access_token,
            request,
            shorthand,
            federation_auth_origin,
        )

    def render(self, request):
        """
        Render a request against the resources registered by the test class's
        servlets.

        Args:
            request (synapse.http.site.SynapseRequest): The request to render.
        """
        render(request, self.resource, self.reactor)

    def setup_test_identity_server(self, *args, **kwargs):
        """
        Set up the test homeserver, meant to be called by the overridable
        make_homeserver. It automatically passes through the test class's
        clock & reactor.

        Args:
            See tests.utils.setup_test_homeserver.

        Returns:
            synapse.server.HomeServer
        """
        kwargs = dict(kwargs)
        if "config" not in kwargs:
            config = self.default_config()
        else:
            config = kwargs["config"]

        ident_server = setup_test_identity_server(config=config, reactor=self.reactor)

        return ident_server

    def get_success(self, d, by=0.0):
        if not isinstance(d, Deferred):
            return d
        self.pump(by=by)
        return self.successResultOf(d)

    def get_failure(self, d, exc):
        """
        Run a Deferred and get a Failure from it. The failure must be of the type `exc`.
        """
        if not isinstance(d, Deferred):
            return d
        self.pump()
        return self.failureResultOf(d, exc)
