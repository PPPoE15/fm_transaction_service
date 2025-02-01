#!/bin/bash

set -e

path_to_run_from=${1:-/opt/python-template}
path_alembic=${2:-/opt/acm/venvs/python-template/bin}
path_alembic_ini=${3:-/opt/acm/venvs/python-template/lib/python3.7/site-packages}


cd "$path_to_run_from"

"$path_alembic"/alembic \
  -c "$path_alembic_ini"/alembic.ini \
  upgrade head

cd -
