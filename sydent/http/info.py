# -*- coding: utf-8 -*-

# copyright 2019 new vector ltd
#
# licensed under the apache license, version 2.0 (the "license");
# you may not use this file except in compliance with the license.
# you may obtain a copy of the license at
#
#     http://www.apache.org/licenses/license-2.0
#
# unless required by applicable law or agreed to in writing, software
# distributed under the license is distributed on an "as is" basis,
# without warranties or conditions of any kind, either express or implied.
# see the license for the specific language governing permissions and
# limitations under the license.

import logging
import re
import copy
import yaml

from netaddr import IPAddress
from sydent.db.invite_tokens import JoinTokenStore

logger = logging.getLogger(__name__)

class Info():

    def __init__(self, syd):
        self.sydent = syd

        try:
            file = open('info.yaml')
            self.config = yaml.load(file)
            file.close()

            # medium:
            #   email:
            #     entries:
            #       matthew@matrix.org: { hs: 'matrix.org', shadow_hs: 'shadow-matrix.org' }
            #     patterns:
            #       - .*@matrix.org: { hs: 'matrix.org', shadow_hs: 'shadow-matrix.org' }

        except Exception as e:
            logger.error(e)

    def match_user_id(medium, address):
        """Return information for a given medium/address combination.

        :param medium: The medium of the address.
        :type medium: str
        :param address: The address of the 3PID.
        :type address: str
        :returns a dict
        """
        result = {}

        # Find an entry in the info file matching this user's ID
        if address in self.config['medium']['email']['entries']:
            result = self.config['medium']['email']['entries'][address]
        else:
            for pattern_group in self.config['medium']['email']['patterns']:
                for pattern in pattern_group:
                    if (re.match("^" + pattern + "$", address)):
                        result = pattern_group[pattern]
                        break
                if result:
                    break

        # Change output if user is from a shadow homeserver
        if self.sydent.nonshadow_ips:
            ip = IPAddress(self.sydent.ip_from_request(request))

            # Present shadow_hs as hs if user is from a shadow server
            if (ip not in self.sydent.nonshadow_ips):
                result['hs'] = result['shadow_hs']
                result.pop('shadow_hs', None)
            else:
                result.setdefault('shadow_hs', '')

        return result