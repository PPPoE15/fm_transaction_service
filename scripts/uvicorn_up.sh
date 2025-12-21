#!/bin/bash
set -e

SERVICE_NAME=$(basename "$PWD")
UVICORN_PORT=${UVICORN_PORT:-80}
ENV_FILE=${ENV_FILE:-dev.env}

alembic_ini_dir=$(find . -name "alembic.ini" -type f | head -1 | xargs -r dirname)

# Generate env file
cp template.env ${ENV_FILE}

# Run migration when `DO_MIGRATION` is not `FALSE` and `alembic.ini` is found
if [[ ! "${DO_MIGRATION,,}" =~ ^(false|no|0)$ ]]; then
    echo "Init migrations from directory path ${alembic_ini_dir}..."
    if [[ -n "${alembic_ini_dir}" ]]; then
      cd "${alembic_ini_dir}"
      alembic upgrade head
      cd -
    else
      echo "The file alembic.ini must exist when DO_MIGRATION is ${DO_MIGRATION}!"
      exit 2
    fi
fi

# Run app
START_CMD="uvicorn --app-dir src --host 0.0.0.0 --port ${UVICORN_PORT} apps.web.main:app"
if [[ "$DEBUGPY_ENABLE" == "1" ]]; then
    START_CMD="debugpy --listen 0.0.0.0:5678 -m ${START_CMD} --reload"
fi
eval "${START_CMD}"