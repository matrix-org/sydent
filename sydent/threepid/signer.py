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

from typing import TYPE_CHECKING, Any, Dict

import signedjson.sign

if TYPE_CHECKING:
    from sydent.sydent import Sydent
    from sydent.threepid import ThreepidAssociation


class Signer:
    def __init__(self, sydent: "Sydent") -> None:
        self.sydent = sydent

    def signedThreePidAssociation(self, assoc: "ThreepidAssociation") -> Dict[str, Any]:
        """
        Signs a 3PID association.

        :param assoc: The association to sign.

        :return: A signed representation of the association.
        """
        sgassoc = {
            "medium": assoc.medium,
            "address": assoc.address,
            "mxid": assoc.mxid,
            "ts": assoc.ts,
            "not_before": assoc.not_before,
            "not_after": assoc.not_after,
        }
        sgassoc.update(assoc.extra_fields)
        sgassoc = signedjson.sign.sign_json(
            sgassoc, self.sydent.config.general.server_name, self.sydent.keyring.ed25519
        )
        return sgassoc
