#!/usr/bin/env bash

set -eu

echo "Running ruff.."
ruff check --config=pyproject.toml src/

echo "Running mypy..."
mypy --config-file=pyproject.toml src/
