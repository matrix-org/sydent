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

import syutil.crypto.jsonsign


def signedThreePidAssociation(sydent, medium, address, mxId, not_before, not_after):
    sgassoc = { 'medium' : medium,
                'address' : address,
                'mxid' : mxId,
                'not_before':not_before,
                'not_after':not_after
              }
    sgassoc = syutil.jsonsign.sign_json(sgassoc, sydent.server_name, sydent.keyring.ed25519)
    return sgassoc


def verifyThreePidAssociationFromHere(sydent, sgassoc):
    """
    Verifies that this association signature is from *this* server
    """
    syutil.jsonsign.verify_signed_json(sgassoc, sydent.server_name, sydent.keyring.ed25519)
