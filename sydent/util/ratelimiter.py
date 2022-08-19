#  Copyright 2022 The Matrix.org Foundation C.I.C.
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from typing import Dict, Generic, TypeVar

from twisted.internet import task
from twisted.internet.interfaces import IReactorTime

K = TypeVar("K")


class LimitExceededException(Exception):
    def __init__(self) -> None:
        super().__init__("Too many requests")


class Ratelimiter(Generic[K]):
    def __init__(self, reactor: IReactorTime, burst: int, rate_hz: float) -> None:
        self._burst = burst

        self._buckets: Dict[K, int] = {}

        call = task.LoopingCall(self._periodic_call)
        call.clock = reactor
        call.start(1 / rate_hz)

    def _periodic_call(self) -> None:
        self._buckets = {
            key: tokens - 1 for key, tokens in self._buckets.items() if tokens > 1
        }

    def ratelimit(self, key: K) -> None:
        current_tokens = self._buckets.get(key, 0)
        if current_tokens >= self._burst:
            raise LimitExceededException()

        self._buckets[key] = current_tokens + 1
