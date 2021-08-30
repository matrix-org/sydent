# Copyright 2014 OpenMarket Ltd.
# Copyright 2018 New Vector Ltd.
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

import os
import re

from setuptools import find_packages, setup


def read_version():
    fn = os.path.join(os.path.dirname(__file__), "sydent", "__init__.py")
    with open(fn) as fp:
        f = fp.read()
    return re.search(r'^__version__ = "(.*)"', f).group(1)


# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name="matrix-sydent",
    version=read_version(),
    packages=find_packages(),
    description="Reference Matrix Identity Verification and Lookup Server",
    python_requires=">=3.6",
    install_requires=[
        "jinja2>=3.0.0",
        "signedjson==1.1.1",
        "unpaddedbase64==1.1.0",
        "Twisted>=18.4.0",
        # twisted warns about about the absence of this
        "service_identity>=1.0.0",
        "phonenumbers",
        "pyopenssl",
        "attrs>=19.1.0",
        "netaddr>=0.7.0",
        "sortedcontainers>=2.1.0",
        "pyyaml>=3.11",
        "flake8==3.9.2",
        "black==21.6b0",
        "isort==5.8.0",
        "mypy>=0.902",
        "mypy-zope>=0.3.1",
        "types-PyYAML",
        "types-mock",
    ],
    # make sure we package the sql files
    include_package_data=True,
    long_description=read("README.rst"),
)
