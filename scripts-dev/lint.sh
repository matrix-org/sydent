#! /usr/bin/env bash
set -ex

# We don't list explicit directories here. Instead, rely on the tools' default behaviour
# (or explicit configuration in setup.cfg/pyproject.toml). This helps to keep this script
# consistent with CI.

black .
# --quiet suppresses the update check.
ruff --quiet .
isort .
mypy
