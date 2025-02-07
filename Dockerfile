ARG DOCKER_REGISTRY="docker.io"

ARG SERVICE_NAME="financial_manager_service"
ARG WORKING_DIR="/opt/${SERVICE_NAME}"

ARG VIRTUAL_ENV="/opt/venv"

FROM ${DOCKER_REGISTRY}/python-pip:v3.7_6 AS common

ARG VIRTUAL_ENV
ENV LANG=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ="Europe/Moscow" \
    VIRTUAL_ENV=${VIRTUAL_ENV} \
    PATH="${VIRTUAL_ENV}/bin:${PATH}"

FROM common AS testing

COPY requirements.txt ./

RUN python3 -m venv "${VIRTUAL_ENV}" \
    \
    && python3 -m pip install --upgrade pip \
    && python3 -m pip install --no-cache-dir -r requirements.txt \
    \
    && apt-get autoremove --purge --yes \
    && apt-get clean

ARG WORKING_DIR
COPY . ${WORKING_DIR}
WORKDIR ${WORKING_DIR}
