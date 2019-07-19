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
import re

import ConfigParser
from inspect import getcallargs

from twisted.internet import defer, reactor

from sydent.sydent import CONFIG_DEFAULTS, Sydent
from tests.logcontext import LoggingContext

logger = logging.getLogger(__name__)


def default_config(name):
    """
    Create a reasonable test config.
    """
    config_dict = CONFIG_DEFAULTS

    config_dict['general']['name'] = name
    config_dict['crypto']['signing_key'] = 'ed25519 a_lPym qvioDNmfExFBRPgdTU+wtFYKq4JfwFRv7sYVgWvmgJg'
    config_dict['db']['db.file'] = ':memory:'

    cfg = ConfigParser.SafeConfigParser()

    for sect, entries in config_dict.items():
        cfg.add_section(sect)
        for k, v in entries.items():
            cfg.set(sect, k, v)

    return cfg


def setup_test_identity_server(
    name="test",
    config=None,
    reactor=None,
    **kargs
):
    if config is None:
        config = default_config(name)

    ident_server = Sydent(cfg=config, reactor=reactor, test=True, **kargs)

    return ident_server


def _format_call(args, kwargs):
    return ", ".join(
        ["%r" % (a) for a in args] + ["%s=%r" % (k, v) for k, v in kwargs.items()]
    )


_hexdig = '0123456789ABCDEFabcdef'
_hextobyte = None


def unquote_to_bytes(string):
    """unquote_to_bytes('abc%20def') -> b'abc def'."""
    # Note: strings are encoded as UTF-8. This is only an issue if it contains
    # unescaped non-ASCII characters, which URIs should not.
    if not string:
        # Is it a string-like object?
        string.split
        return b''
    if isinstance(string, str):
        string = string.encode('utf-8')
    bits = string.split(b'%')
    if len(bits) == 1:
        return string
    res = [bits[0]]
    append = res.append
    # Delay the initialization of the table to not waste memory
    # if the function is never called
    global _hextobyte
    if _hextobyte is None:
        _hextobyte = {(a + b).encode(): bytes.fromhex(a + b)
                      for a in _hexdig for b in _hexdig}
    for item in bits[1:]:
        try:
            append(_hextobyte[item[:2]])
            append(item[2:])
        except KeyError:
            append(b'%')
            append(item)
    return b''.join(res)


_asciire = re.compile('([\x00-\x7f]+)')


def unquote(string, encoding='utf-8', errors='replace'):
    """Replace %xx escapes by their single-character equivalent. The optional
    encoding and errors parameters specify how to decode percent-encoded
    sequences into Unicode characters, as accepted by the bytes.decode()
    method.
    By default, percent-encoded sequences are decoded with UTF-8, and invalid
    sequences are replaced by a placeholder character.

    unquote('abc%20def') -> 'abc def'.
    """
    if '%' not in string:
        string.split
        return string
    if encoding is None:
        encoding = 'utf-8'
    if errors is None:
        errors = 'replace'
    bits = _asciire.split(string)
    res = [bits[0]]
    append = res.append
    for i in range(1, len(bits), 2):
        append(unquote_to_bytes(bits[i]).decode(encoding, errors))
        append(bits[i + 1])
    return ''.join(res)
