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


def threePidAssocFromDict(d):
    """
    Instantiates a ThreepidAssociation from the given dict.

    :param d: The dict to use when instantiating the ThreepidAssociation.
    :type d: dict[str, any]

    :return: The instantiated ThreepidAssociation.
    :rtype: ThreepidAssociation
    """
    assoc = ThreepidAssociation(
        d["medium"],
        d["address"],
        None,  # empty lookup_hash digest by default
        d["mxid"],
        d["ts"],
        d["not_before"],
        d["not_after"],
    )
    return assoc


class ThreepidAssociation:
    def __init__(self, medium, address, lookup_hash, mxid, ts, not_before, not_after):
        """
        :param medium: The medium of the 3pid (eg. email)
        :param address: The identifier (eg. email address)
        :param lookup_hash: A hash digest of the 3pid. Can be a str or None
        :param mxid: The matrix ID the 3pid is associated with
        :param ts: The creation timestamp of this association, ms
        :param not_before: The timestamp, in ms, at which this association becomes valid
        :param not_after: The timestamp, in ms, at which this association ceases to be valid
        """
        self.medium = medium
        self.address = address
        self.lookup_hash = lookup_hash
        self.mxid = mxid
        self.ts = ts
        self.not_before = not_before
        self.not_after = not_after
        self.extra_fields = {}
