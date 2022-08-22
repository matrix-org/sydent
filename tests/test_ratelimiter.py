# Copyright 2022 The Matrix.org Foundation C.I.C.
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


from twisted.test.proto_helpers import MemoryReactorClock
from twisted.trial import unittest

from sydent.util.ratelimiter import LimitExceededException, Ratelimiter


class RatelimiterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = MemoryReactorClock()
        self.ratelimiter = Ratelimiter(self.clock, burst=5, rate_hz=0.5)

    def test_simple(self) -> None:
        """Test that a request doesn't get ratelimited to start off with"""
        key = "key"

        # This should not raise as we're below the ratelimit
        self.ratelimiter.ratelimit(key)

    def test_burst(self) -> None:
        """Test that we can send `burst` number of messages before getting
        ratelimited
        """
        key = "key"

        # This should not raise as we're below the ratelimit
        for _ in range(5):
            self.ratelimiter.ratelimit(key)

        with self.assertRaises(LimitExceededException):
            self.ratelimiter.ratelimit(key)

    def test_burst_reset(self) -> None:
        """Test that once we hit the ratelimit we can wait a while and we'll be
        able to send requests again
        """
        key = "key"

        # This should not raise as we're below the ratelimit
        for _ in range(5):
            self.ratelimiter.ratelimit(key)

        with self.assertRaises(LimitExceededException):
            self.ratelimiter.ratelimit(key)

        self.clock.pump([2.0] * 5)

        for _ in range(5):
            self.ratelimiter.ratelimit(key)

        with self.assertRaises(LimitExceededException):
            self.ratelimiter.ratelimit(key)

    def test_average_rate(self):
        """Test that sending requests at a rate higher than the maximum rate
        gets ratelimited.
        """
        key = "key"

        with self.assertRaises(LimitExceededException):
            for _ in range(100):
                self.clock.advance(1)
                self.ratelimiter.ratelimit(key)

    def test_average_rate_burst(self):
        """Test that if we go above the maximum rate we'll get ratelimited"""
        key = "key"

        for _ in range(5):
            self.ratelimiter.ratelimit(key)

        for _ in range(100):
            self.clock.advance(2)
            self.ratelimiter.ratelimit(key)

        with self.assertRaises(LimitExceededException):
            self.ratelimiter.ratelimit(key)
