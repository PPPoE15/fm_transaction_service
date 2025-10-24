#!/bin/bash
set -e

(source .ci_env && envsubst < template.env > dev.env)

UVICORN_PORT=${UVICORN_PORT:-80}

if [[ $# -eq 0 ]] ; then
    echo 'No arguments given...This is the way!'

    if [[ "${DO_MIGRATION,,}" == "true" || "${DO_MIGRATION,,}" == "yes" ]]; then
	    echo "Init migrations..."
	    cd ./src
	    dotenv --file ../dev.env run alembic upgrade head
	    cd -
    fi

elif [ "$1" == "manual" ]; then
    echo "Manual mode activated..."
    apt-get update && apt-get install -y openssh-client python3.11-dev gcc gettext-base libpq5
    python3 -m pip install --upgrade pip
    pip3 install -r ./requirements.txt
    docker_secrets_folder=/run/secrets/
    mkdir -p "$docker_secrets_folder"

else
    echo -e "Unrecognized argument is given. \nExpected 'manual' or just nothing"
fi

START_CMD="uvicorn --app-dir src --host 0.0.0.0 --port ${UVICORN_PORT} apps.web.main:app --env-file dev.env --log-level warning"
if [[ "$DEBUGPY_ENABLE" == "1" ]]; then
    START_CMD="debugpy --listen 0.0.0.0:5678 -m ${START_CMD} --reload"
fi

eval "${START_CMD}"