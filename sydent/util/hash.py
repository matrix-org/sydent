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

import hashlib
import unpaddedbase64


def sha256_and_url_safe_base64(input_text):
    """SHA256 hash an input string, encode the digest as url-safe base64, and return"""
    digest = hashlib.sha256(input_text.encode()).digest()
    return unpaddedbase64.encode_base64(digest, urlsafe=True)

def parse_space_separated_str(self, input_str):
    """Parses a string containing values seperated by a space. Joins the leading chunks if there are more than two.

    Used for parsing medium, address values.

    e.g. If given input_str="someaddress somemedium",
    this function will return ("someaddress", "somemedium").

    If given input_str="some address somemedium",
    this function will return ("some address", "somemedium").

    This is due to the future possibility of address values containing
    spaces.

    :param input_str: The space-separated str to split
    :type input_str: str

    :returns a list with 2 strings in it
    :rtype [str, str]
    """
    # Split the string by spaces
    split_input = input_str.split()

    # Return the last item separated from the rest
    return (' '.join(split_input[:-1]), split_input[-1])

def diff_lists(first, second):
    """Returns any differences between two lists

    :param first: A list of items
    :type first: List

    :param second: Another list of items
    :type second: List

    :returns a list containing items not found in both lists
    :rtype: List
    """
    a_minus_b = [x for x in first if x not in second]
    b_minus_a = [x for x in second if x not in first]
    return a_minus_b + b_minus_a
