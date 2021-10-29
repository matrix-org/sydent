#! /usr/bin/env bash
set -ex

black sydent/ stubs/ tests/ matrix_is_test/ scripts/ setup.py
flake8 sydent/ tests/ matrix_is_test/ scripts/ setup.py
flake8 stubs/ --ignore E
isort sydent/ stubs/ tests/ matrix_is_test/ scripts/ setup.py
mypy
