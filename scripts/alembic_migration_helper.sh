#!/bin/bash

set -e

path_to_run_from=${1:-/opt/pfinancial_manager}
path_alembic=${2:-/opt/venvs/financial_manager/bin}
path_alembic_ini=${3:-/opt/venvs/financial_manager/lib/python3.7/site-packages}


cd "$path_to_run_from"

"$path_alembic"/alembic \
  -c "$path_alembic_ini"/alembic.ini \
  upgrade head

cd -
