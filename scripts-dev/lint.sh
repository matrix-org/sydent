#! /usr/bin/env bash
set -ex

black sydent/ stubs/ tests/ matrix_is_test/ scripts/ setup.py
flake8 sydent/ stubs/ tests/ matrix_is_test/ scripts/ setup.py
isort sydent/ stubs/ tests/ matrix_is_test/ scripts/ setup.py
mypy
