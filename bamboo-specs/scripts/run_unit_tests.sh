#!/bin/bash

set -eu

tmp="$(mktemp)"

# sh has limitations in the source vars from files
# hence we need to have that ugly workaround
cp bamboo-vars/.env-common "$tmp"
sed -i '/req_services/d' "$tmp"
. "$tmp"
rm "$tmp"

echo "Installing python-dotenv..."
python3 -m pip install python-dotenv[cli]

# specify .ci_unit_env first, so that it has a priority over .ci_env file
source <(cat .ci_unit_env .ci_env) && envsubst < template.env > dev.env

echo "Running Unit Tests..."
dotenv --file ./dev.env run pytest src/tests
