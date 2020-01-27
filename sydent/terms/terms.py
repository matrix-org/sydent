# -*- coding: utf-8 -*-

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
import yaml


logger = logging.getLogger(__name__)


class Terms(object):
    def __init__(self, yamlObj):
        """
        :param yamlObj: The parsed YAML.
        :type yamlObj: dict[str, any] or None
        """
        self._rawTerms = yamlObj

    def getMasterVersion(self):
        """
        :return: The global (master) version of the terms, or None if there
            are no terms of service for this server.
        :rtype: unicode or None
        """
        version = None if self._rawTerms is None else self._rawTerms['master_version']

        # Ensure we're dealing with unicode.
        if version and isinstance(version, bytes):
            version = version.decode("UTF-8")

        return version

    def getForClient(self):
        """
        :return: A dict which value for the "policies" key is a dict which contains the
            "docs" part of the terms' YAML. That nested dict is empty if no terms.
        :rtype: dict[str, dict]
        """
        policies = {}
        if self._rawTerms is not None:
            for docName, doc in self._rawTerms['docs'].items():
                policies[docName] = {
                    'version': doc['version'],
                }
                policies[docName].update(doc['langs'])
        return { 'policies': policies }

    def getUrlSet(self):
        """
        :return: All the URLs for the terms in a set. Empty set if no terms.
        :rtype: set[unicode]
        """
        urls = set()
        if self._rawTerms is not None:
            for docName, doc in self._rawTerms['docs'].items():
                for langName, lang in doc['langs'].items():
                    url = lang['url']

                    # Ensure we're dealing with unicode.
                    if url and isinstance(url, bytes):
                        url = url.decode("UTF-8")

                    urls.add(url)
        return urls

    def urlListIsSufficient(self, urls):
        """
        Checks whether the provided list of URLs (which represents the list of terms
        accepted by the user) is enough to allow the creation of the user's account.

        :param urls: The list of URLs of terms the user has accepted.
        :type urls: list[unicode]

        :return: Whether the list is sufficient to allow the creation of the user's
            account.
        :rtype: bool
        """
        agreed = set()
        urlset = set(urls)

        if self._rawTerms is not None:
            for docName, doc in self._rawTerms['docs'].items():
                for lang in doc['langs'].values():
                    if lang['url'] in urlset:
                        agreed.add(docName)
                        break

        required = set(self._rawTerms['docs'].keys())
        return agreed == required

def get_terms(sydent):
    """Read and parse terms as specified in the config.

    :returns Terms
    """
    try:
        termsYaml = None
        termsPath = sydent.cfg.get('general', 'terms.path')
        if termsPath == '':
            return Terms(None)

        with open(termsPath) as fp:
            termsYaml = yaml.full_load(fp)
        if 'master_version' not in termsYaml:
            raise Exception("No master version")
        if 'docs' not in termsYaml:
            raise Exception("No 'docs' key in terms")
        for docName, doc in termsYaml['docs'].items():
            if 'version' not in doc:
                raise Exception("'%s' has no version" % (docName,))
            if 'langs' not in doc:
                raise Exception("'%s' has no langs" % (docName,))
            for langKey, lang in doc['langs'].items():
                if 'name' not in lang:
                    raise Exception("lang '%s' of doc %s has no name" % (langKey, docName))
                if 'url' not in lang:
                    raise Exception("lang '%s' of doc %s has no url" % (langKey, docName))

        return Terms(termsYaml)
    except Exception:
        logger.exception("Couldn't read terms file '%s'", sydent.cfg.get('general', 'terms.path'))
