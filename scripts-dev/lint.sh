#! /usr/bin/env bash
set -ex

black sydent/ tests/ matrix_is_test/ scripts/ setup.py
flake8 sydent/ tests/ matrix_is_test/ scripts/ setup.py
isort sydent/ tests/ matrix_is_test/ scripts/ setup.py
mypy
