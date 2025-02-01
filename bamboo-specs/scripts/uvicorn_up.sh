#!/bin/bash
set -e

source .ci_env && envsubst < template.env > dev.env

#SERVICE_NAME=$(pwd | sed 's/\/srv\///')
#mkdir -p "/opt/acm/$SERVICE_NAME-data"

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
    PYPI_REPO="https://artifactory.astralinux.ru/artifactory/api/pypi/acmp-pypi-packages/simple"
    apt-get update && apt-get install -y openssh-client python3.7-dev gcc gettext-base libpq5
    python3 -m pip install --upgrade pip
    pip3 install -i ${PYPI_REPO} -r ./requirements.txt
    docker_secrets_folder=/run/secrets/
    mkdir -p "$docker_secrets_folder"

else
    echo -e "Unrecognized argument is given. \nExpected 'manual' or just nothing"
fi
uvicorn --app-dir src --host "0.0.0.0" --port 80 "modules.web.main:app" --env-file ./dev.env
