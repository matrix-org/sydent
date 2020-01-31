# -*- coding: utf-8 -*-

# Copyright 2018 Travis Ralston
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
from __future__ import absolute_import

from twisted.web.resource import Resource

from sydent.http.servlets import jsonwrap, send_cors


class V1Servlet(Resource):
    isLeaf = False

    def __init__(self, syd):
        Resource.__init__(self)
        self.sydent = syd

    @jsonwrap
    def render_GET(self, request):
        send_cors(request)
        return {}

    def render_OPTIONS(self, request):
        send_cors(request)
        return b''
