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

import logging
from typing import TYPE_CHECKING, Dict, List, Mapping, Optional, Set, Union

import yaml
from typing_extensions import TypedDict

if TYPE_CHECKING:
    from sydent.sydent import Sydent

logger = logging.getLogger(__name__)


class TermConfig(TypedDict):
    master_version: str
    docs: Mapping[str, "Policy"]


class Policy(TypedDict):
    version: str
    langs: Mapping[str, "LocalisedPolicy"]


class LocalisedPolicy(TypedDict):
    name: str
    url: str


VersionOrLang = Union[str, LocalisedPolicy]


class Terms:
    def __init__(self, yamlObj: Optional[TermConfig]) -> None:
        """
        :param yamlObj: The parsed YAML.
        """
        self._rawTerms = yamlObj

    def getMasterVersion(self) -> Optional[str]:
        """
        :return: The global (master) version of the terms, or None if there
            are no terms of service for this server.
        """
        if self._rawTerms is None:
            return None
        return self._rawTerms["master_version"]

    def getForClient(self) -> Dict[str, Dict[str, Dict[str, VersionOrLang]]]:
        # Examples:
        # "policy" -> "terms_of_service", "version" -> "1.2.3"
        # "policy" -> "terms_of_service", "en" -> LocalisedPolicy
        """
        :return: A dict which value for the "policies" key is a dict which contains the
            "docs" part of the terms' YAML. That nested dict is empty if no terms.
        """
        policies: Dict[str, Dict[str, VersionOrLang]] = {}
        if self._rawTerms is not None:
            for docName, doc in self._rawTerms["docs"].items():
                policies[docName] = {
                    "version": doc["version"],
                }
                policies[docName].update(doc["langs"])
        return {"policies": policies}

    def getUrlSet(self) -> Set[str]:
        """
        :return: All the URLs for the terms in a set. Empty set if no terms.
        """
        urls = set()
        if self._rawTerms is not None:
            for docName, doc in self._rawTerms["docs"].items():
                for langName, lang in doc["langs"].items():
                    url = lang["url"]
                    urls.add(url)
        return urls

    def urlListIsSufficient(self, urls: List[str]) -> bool:
        """
        Checks whether the provided list of URLs (which represents the list of terms
        accepted by the user) is enough to allow the creation of the user's account.

        :param urls: The list of URLs of terms the user has accepted.

        :return: Whether the list is sufficient to allow the creation of the user's
            account.
        """
        agreed = set()
        urlset = set(urls)

        if self._rawTerms is None:
            if urls:
                raise ValueError("No configured terms, but user accepted some terms")
            else:
                return True

        else:
            for docName, doc in self._rawTerms["docs"].items():
                for lang in doc["langs"].values():
                    if lang["url"] in urlset:
                        agreed.add(docName)
                        break

            required = set(self._rawTerms["docs"].keys())
            return agreed == required


def get_terms(sydent: "Sydent") -> Terms:
    """Read and parse terms as specified in the config.

    Errors in reading, parsing and validating the config
    are raised as exceptions."""
    # TODO - move some of this to parse_config

    termsPath = sydent.config.general.terms_path

    if termsPath == "":
        return Terms(None)

    with open(termsPath) as fp:
        termsYaml = yaml.safe_load(fp)

    # TODO use something like jsonschema instead of this handwritten code.
    if "master_version" not in termsYaml:
        raise Exception("No master version")
    elif not isinstance(termsYaml["master_version"], str):
        raise TypeError(
            f"master_version should be a string, not {termsYaml['master_version']!r}"
        )
    if "docs" not in termsYaml:
        raise Exception("No 'docs' key in terms")
    for docName, doc in termsYaml["docs"].items():
        if "version" not in doc:
            raise Exception("'%s' has no version" % (docName,))
        if "langs" not in doc:
            raise Exception("'%s' has no langs" % (docName,))
        for langKey, lang in doc["langs"].items():
            if "name" not in lang:
                raise Exception("lang '%s' of doc %s has no name" % (langKey, docName))
            if "url" not in lang:
                raise Exception("lang '%s' of doc %s has no url" % (langKey, docName))

    return Terms(termsYaml)
