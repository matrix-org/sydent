# Copyright 2021 The Matrix.org Foundation C.I.C.
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

from configparser import BasicInterpolation, ConfigParser, Interpolation


class SydentInterpolation(Interpolation):
    """Interpolation that uses BasicInterpolation with a blacklist"""

    # Options to never interpolate for backwards compatablility
    BLACLIST = ["email.invite.subject", "email.invite.subject_space"]

    # The BasicInterpolation object to use
    _basic_interpolation = BasicInterpolation()

    def before_get(self, parser, section, option, value, defaults):
        if option in self.BLACLIST:
            return value
        else:
            return self._basic_interpolation.before_get(
                parser, section, option, value, defaults
            )

    def before_set(self, parser, section, option, value):
        if option in self.BLACLIST:
            return value
        else:
            return self._basic_interpolation.before_set(parser, section, option, value)

    def before_read(self, parser, section, option, value):
        if option in self.BLACLIST:
            return value
        else:
            return self._basic_interpolation.before_read(parser, section, option, value)

    def before_write(self, parser, section, option, value):
        if option in self.BLACLIST:
            return value
        else:
            return self._basic_interpolation.before_write(
                parser, section, option, value
            )


class SydentConfigParser(ConfigParser):

    _DEFAULT_INTERPOLATION = SydentInterpolation()
