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
from typing import Any, Dict, Optional

import attr


def threePidAssocFromDict(d: Dict[str, Any]) -> "ThreepidAssociation":
    """Instantiates a ThreepidAssociation from the given dict."""
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


@attr.s(slots=True, auto_attribs=True)
class ThreepidAssociation:
    """
    medium: The medium of the 3pid (eg. email)
    address: The identifier (eg. email address)
    lookup_hash: A hash digest of the 3pid. Can be a str or None
    mxid: The matrix ID the 3pid is associated with
    ts: The creation timestamp of this association, ms
    not_before: The timestamp, in ms, at which this association becomes valid
    not_after: The timestamp, in ms, at which this association ceases to be valid
    """

    medium: str
    address: str
    lookup_hash: Optional[str]
    # Note: the next four fields were made optional in schema version 2.
    # See sydent.db.sqlitedb.SqliteDatabase._upgradeSchema
    mxid: Optional[str]
    ts: Optional[int]
    not_before: Optional[int]
    not_after: Optional[int]
    extra_fields: Dict[str, Any] = {}
