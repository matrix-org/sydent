#! /usr/bin/env bash
set -ex

# Keep this up to date with the CI config at .github/workflows/pipeline.yml

black sydent/ stubs/ tests/ matrix_is_test/ scripts/ setup.py
flake8 sydent/ tests/ matrix_is_test/ scripts/ setup.py

# There's a different convention for formatting stub files.
# Ignore various error codes from pycodestyle that we don't want
# to enforce for stubs. (We rely on `black` to format stubs.)

# E301, E302 and E305 complain about missing blank lines.
# E701 and E7044 complains when we define a function or class entirely within
# one line.
flake8 stubs/ --ignore E301,E302,E305,E701,E704

isort sydent/ stubs/ tests/ matrix_is_test/ scripts/ setup.py
mypy
