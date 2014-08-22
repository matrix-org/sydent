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

import json


def require_args(request, rqArgs):
    missing = []
    for a in rqArgs:
        if a not in request.args:
            missing.append(a)

    if len(missing) > 0:
        request.setResponseCode(400)
        msg = "Missing parameters: "+(",".join(missing))
        return {'errcode': 'M_MISSING_PARAMS', 'error': msg}

def jsonwrap(f):
    def inner(*args, **kwargs):
        return json.dumps(f(*args, **kwargs)).encode("UTF-8")
    return inner

def send_cors(request):
    request.setHeader(b"Content-Type", b"application/json")
    request.setHeader("Access-Control-Allow-Origin", "*")
    request.setHeader("Access-Control-Allow-Methods",
                      "GET, POST, PUT, DELETE, OPTIONS")
    request.setHeader("Access-Control-Allow-Headers",
                      "Origin, X-Requested-With, Content-Type, Accept")