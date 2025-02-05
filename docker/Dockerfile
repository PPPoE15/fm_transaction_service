ARG DOCKER_REGISTRY="docker.io"

ARG SERVICE_NAME="financial_manager"
ARG WORKING_DIR="/opt/${SERVICE_NAME}"

ARG VIRTUAL_ENV="/opt/venv"

FROM ${DOCKER_REGISTRY}/unit:python3.11 AS common

ARG VIRTUAL_ENV
ENV LANG=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ="Europe/Moscow" \
    VIRTUAL_ENV=${VIRTUAL_ENV} \
    PATH="${VIRTUAL_ENV}/bin:${PATH}"

RUN apt-get update \
    && apt-get install --no-install-recommends -y python3-pip \
    && apt-get clean

FROM common as development-env

ARG WORKING_DIR
WORKDIR ${WORKING_DIR}

COPY modules/ ./

RUN buildDeps="python3-dev python3-venv gcc libpq5" \
    && apt-get update && apt-get install --no-install-recommends -y ${buildDeps} \
    && python3 -m venv "${VIRTUAL_ENV}" \
    && python3 -m pip install --upgrade pip \
    \
    && pip install pip-tools \
    && pip-compile --output-file requirements.txt requirements-dev.in \
    && python3 -m pip install --no-cache-dir -r requirements.txt \
    \
    && apt-get autoremove --purge --yes \
    && apt-get clean
