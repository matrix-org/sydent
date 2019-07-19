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

""" Thread-local-alike tracking of log contexts within synapse

This module provides objects and utilities for tracking contexts through
synapse code, so that log lines can include a request identifier, and so that
CPU and database activity can be accounted for against the request that caused
them.

See doc/log_contexts.rst for details on how this works.
"""

import logging
import threading

from twisted.internet import defer, threads

logger = logging.getLogger(__name__)

try:
    import resource

    # Python doesn't ship with a definition of RUSAGE_THREAD but it's defined
    # to be 1 on linux so we hard code it.
    RUSAGE_THREAD = 1

    # If the system doesn't support RUSAGE_THREAD then this should throw an
    # exception.
    resource.getrusage(RUSAGE_THREAD)

    def get_thread_resource_usage():
        return resource.getrusage(RUSAGE_THREAD)
except Exception:
    # If the system doesn't support resource.getrusage(RUSAGE_THREAD) then we
    # won't track resource usage by returning None.
    def get_thread_resource_usage():
        return None


class ContextResourceUsage(object):
    """Object for tracking the resources used by a log context

    Attributes:
        ru_utime (float): user CPU time (in seconds)
        ru_stime (float): system CPU time (in seconds)
        db_txn_count (int): number of database transactions done
        db_sched_duration_sec (float): amount of time spent waiting for a
            database connection
        db_txn_duration_sec (float): amount of time spent doing database
            transactions (excluding scheduling time)
        evt_db_fetch_count (int): number of events requested from the database
    """

    __slots__ = [
        "ru_stime", "ru_utime",
        "db_txn_count", "db_txn_duration_sec", "db_sched_duration_sec",
        "evt_db_fetch_count",
    ]

    def __init__(self, copy_from=None):
        """Create a new ContextResourceUsage

        Args:
            copy_from (ContextResourceUsage|None): if not None, an object to
                copy stats from
        """
        if copy_from is None:
            self.reset()
        else:
            self.ru_utime = copy_from.ru_utime
            self.ru_stime = copy_from.ru_stime
            self.db_txn_count = copy_from.db_txn_count

            self.db_txn_duration_sec = copy_from.db_txn_duration_sec
            self.db_sched_duration_sec = copy_from.db_sched_duration_sec
            self.evt_db_fetch_count = copy_from.evt_db_fetch_count

    def copy(self):
        return ContextResourceUsage(copy_from=self)

    def reset(self):
        self.ru_stime = 0.
        self.ru_utime = 0.
        self.db_txn_count = 0

        self.db_txn_duration_sec = 0
        self.db_sched_duration_sec = 0
        self.evt_db_fetch_count = 0

    def __repr__(self):
        return ("<ContextResourceUsage ru_stime='%r', ru_utime='%r', "
                "db_txn_count='%r', db_txn_duration_sec='%r', "
                "db_sched_duration_sec='%r', evt_db_fetch_count='%r'>") % (
                    self.ru_stime,
                    self.ru_utime,
                    self.db_txn_count,
                    self.db_txn_duration_sec,
                    self.db_sched_duration_sec,
                    self.evt_db_fetch_count,)

    def __iadd__(self, other):
        """Add another ContextResourceUsage's stats to this one's.

        Args:
            other (ContextResourceUsage): the other resource usage object
        """
        self.ru_utime += other.ru_utime
        self.ru_stime += other.ru_stime
        self.db_txn_count += other.db_txn_count
        self.db_txn_duration_sec += other.db_txn_duration_sec
        self.db_sched_duration_sec += other.db_sched_duration_sec
        self.evt_db_fetch_count += other.evt_db_fetch_count
        return self

    def __isub__(self, other):
        self.ru_utime -= other.ru_utime
        self.ru_stime -= other.ru_stime
        self.db_txn_count -= other.db_txn_count
        self.db_txn_duration_sec -= other.db_txn_duration_sec
        self.db_sched_duration_sec -= other.db_sched_duration_sec
        self.evt_db_fetch_count -= other.evt_db_fetch_count
        return self

    def __add__(self, other):
        res = ContextResourceUsage(copy_from=self)
        res += other
        return res

    def __sub__(self, other):
        res = ContextResourceUsage(copy_from=self)
        res -= other
        return res


class LoggingContext(object):
    """Additional context for log formatting. Contexts are scoped within a
    "with" block.

    If a parent is given when creating a new context, then:
        - logging fields are copied from the parent to the new context on entry
        - when the new context exits, the cpu usage stats are copied from the
          child to the parent

    Args:
        name (str): Name for the context for debugging.
        parent_context (LoggingContext|None): The parent of the new context
    """

    __slots__ = [
        "previous_context", "name", "parent_context",
        "_resource_usage",
        "usage_start",
        "main_thread", "alive",
        "request", "tag",
    ]

    thread_local = threading.local()

    class Sentinel(object):
        """Sentinel to represent the root context"""

        __slots__ = []

        def __str__(self):
            return "sentinel"

        def copy_to(self, record):
            pass

        def start(self):
            pass

        def stop(self):
            pass

        def add_database_transaction(self, duration_sec):
            pass

        def add_database_scheduled(self, sched_sec):
            pass

        def record_event_fetch(self, event_count):
            pass

        def __nonzero__(self):
            return False
        __bool__ = __nonzero__  # python3

    sentinel = Sentinel()

    def __init__(self, name=None, parent_context=None, request=None):
        self.previous_context = LoggingContext.current_context()
        self.name = name

        # track the resources used by this context so far
        self._resource_usage = ContextResourceUsage()

        # If alive has the thread resource usage when the logcontext last
        # became active.
        self.usage_start = None

        self.main_thread = threading.current_thread()
        self.request = None
        self.tag = ""
        self.alive = True

        self.parent_context = parent_context

        if self.parent_context is not None:
            self.parent_context.copy_to(self)

        if request is not None:
            # the request param overrides the request from the parent context
            self.request = request

    def __str__(self):
        if self.request:
            return str(self.request)
        return "%s@%x" % (self.name, id(self))

    @classmethod
    def current_context(cls):
        """Get the current logging context from thread local storage

        Returns:
            LoggingContext: the current logging context
        """
        return getattr(cls.thread_local, "current_context", cls.sentinel)

    @classmethod
    def set_current_context(cls, context):
        """Set the current logging context in thread local storage
        Args:
            context(LoggingContext): The context to activate.
        Returns:
            The context that was previously active
        """
        current = cls.current_context()

        if current is not context:
            current.stop()
            cls.thread_local.current_context = context
            context.start()
        return current

    def __enter__(self):
        """Enters this logging context into thread local storage"""
        old_context = self.set_current_context(self)
        if self.previous_context != old_context:
            logger.warn(
                "Expected previous context %r, found %r",
                self.previous_context, old_context
            )
        self.alive = True

        return self

    def __exit__(self, type, value, traceback):
        """Restore the logging context in thread local storage to the state it
        was before this context was entered.
        Returns:
            None to avoid suppressing any exceptions that were thrown.
        """
        current = self.set_current_context(self.previous_context)
        if current is not self:
            if current is self.sentinel:
                logger.warning("Expected logging context %s was lost", self)
            else:
                logger.warning(
                    "Expected logging context %s but found %s", self, current
                )
        self.previous_context = None
        self.alive = False

        # if we have a parent, pass our CPU usage stats on
        if (
            self.parent_context is not None
            and hasattr(self.parent_context, '_resource_usage')
        ):
            self.parent_context._resource_usage += self._resource_usage

            # reset them in case we get entered again
            self._resource_usage.reset()

    def copy_to(self, record):
        """Copy logging fields from this context to a log record or
        another LoggingContext
        """

        # 'request' is the only field we currently use in the logger, so that's
        # all we need to copy
        record.request = self.request

    def start(self):
        if threading.current_thread() is not self.main_thread:
            logger.warning("Started logcontext %s on different thread", self)
            return

        # If we haven't already started record the thread resource usage so
        # far
        if not self.usage_start:
            self.usage_start = get_thread_resource_usage()

    def stop(self):
        if threading.current_thread() is not self.main_thread:
            logger.warning("Stopped logcontext %s on different thread", self)
            return

        # When we stop, let's record the cpu used since we started
        if not self.usage_start:
            logger.warning(
                "Called stop on logcontext %s without calling start", self,
            )
            return

        usage_end = get_thread_resource_usage()

        self._resource_usage.ru_utime += usage_end.ru_utime - self.usage_start.ru_utime
        self._resource_usage.ru_stime += usage_end.ru_stime - self.usage_start.ru_stime

        self.usage_start = None

    def get_resource_usage(self):
        """Get resources used by this logcontext so far.

        Returns:
            ContextResourceUsage: a *copy* of the object tracking resource
                usage so far
        """
        # we always return a copy, for consistency
        res = self._resource_usage.copy()

        # If we are on the correct thread and we're currently running then we
        # can include resource usage so far.
        is_main_thread = threading.current_thread() is self.main_thread
        if self.alive and self.usage_start and is_main_thread:
            current = get_thread_resource_usage()
            res.ru_utime += current.ru_utime - self.usage_start.ru_utime
            res.ru_stime += current.ru_stime - self.usage_start.ru_stime

        return res

    def add_database_transaction(self, duration_sec):
        self._resource_usage.db_txn_count += 1
        self._resource_usage.db_txn_duration_sec += duration_sec

    def add_database_scheduled(self, sched_sec):
        """Record a use of the database pool

        Args:
            sched_sec (float): number of seconds it took us to get a
                connection
        """
        self._resource_usage.db_sched_duration_sec += sched_sec

    def record_event_fetch(self, event_count):
        """Record a number of events being fetched from the db

        Args:
            event_count (int): number of events being fetched
        """
        self._resource_usage.evt_db_fetch_count += event_count
