ARG SERVICE_NAME="financial_manager"
ARG WORKING_DIR="/opt/${SERVICE_NAME}"

ARG VIRTUAL_ENV="/opt/venv"

FROM python:3.13-bullseye AS common

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

FROM common as testing

ARG WORKING_DIR
WORKDIR ${WORKING_DIR}

COPY poetry.lock ./
COPY pyproject.toml ./

RUN apt-get update && apt-get install --no-install-recommends -y python3-venv libpq5 gettext-base

RUN python3 -m venv "${VIRTUAL_ENV}"
RUN python3 -m pip install --upgrade pip
RUN pip install poetry==2.1
RUN poetry install --all-groups --no-cache --no-root
