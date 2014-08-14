# -*- coding: utf-8 -*-

# Copyright 2014 matrix.org
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

import twisted.internet.reactor
import twisted.internet.task

class Pusher:
    def __init__(self, sydent):
        self.sydent = sydent

    def setup(self):
        cb = twisted.internet.task.LoopingCall(Pusher.scheduledPush, self)
        cb.start(10.0)

    def scheduledPush(self):
        print "PUSH!"
