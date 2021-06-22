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

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from sydent.sydent import Sydent


class TermsStore:
    def __init__(self, sydent: "Sydent") -> None:
        self.sydent = sydent

    def getAgreedUrls(self, user_id: str) -> List[str]:
        """
        Retrieves the URLs of the terms the given user has agreed to.

        :param user_id: Matrix user ID to fetch the URLs for.

        :return: A list of the URLs of the terms accepted by the user.
        """
        cur = self.sydent.db.cursor()
        res = cur.execute(
            "select url from accepted_terms_urls " "where user_id = ?",
            (user_id,),
        )

        urls = []
        for (url,) in res:
            # Ensure we're dealing with unicode.
            if url and isinstance(url, bytes):
                url = url.decode("UTF-8")

            urls.append(url)

        return urls

    def addAgreedUrls(self, user_id: str, urls: List[str]) -> None:
        """
        Saves that the given user has accepted the terms at the given URLs.

        :param user_id: The Matrix user ID that has accepted the terms.
        :param urls: The list of URLs.
        """
        cur = self.sydent.db.cursor()
        cur.executemany(
            "insert or ignore into accepted_terms_urls (user_id, url) values (?, ?)",
            ((user_id, u) for u in urls),
        )
        self.sydent.db.commit()
