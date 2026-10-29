ARG PYTHON_IMAGE=python:3.13-slim-bookworm
ARG SERVICE_NAME="fm_transaction_service"
ARG WORKING_DIR="/opt/${SERVICE_NAME}"
ARG VIRTUAL_ENV="/opt/venv"

FROM ${PYTHON_IMAGE} AS common
ARG VIRTUAL_ENV
ENV LANG=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ="Europe/Moscow" \
    VIRTUAL_ENV=${VIRTUAL_ENV} \
    PATH="${VIRTUAL_ENV}/bin:${PATH}"

# curl нужен проверкам Compose, envsubst сохраняется для совместимости запуска.
RUN apt-get update \
    && apt-get install --no-install-recommends -y curl gettext-base tzdata \
    && rm -rf /var/lib/apt/lists/*

FROM common AS builder
# Poetry изолирован от окружения приложения и не переносится в runtime.
RUN python -m venv /opt/poetry \
    && /opt/poetry/bin/pip install poetry==2.1 \
    && python -m venv "${VIRTUAL_ENV}"
WORKDIR /build
COPY poetry.lock pyproject.toml ./

FROM builder AS master-dependencies
RUN /opt/poetry/bin/poetry install --only=common --no-root --no-cache --no-interaction

FROM builder AS dev-dependencies
RUN /opt/poetry/bin/poetry install --all-groups --no-root --no-cache --no-interaction

FROM common AS runtime
ARG WORKING_DIR
WORKDIR ${WORKING_DIR}
COPY template.env ./
COPY src ./src
COPY scripts ./scripts

FROM runtime AS master
COPY --from=master-dependencies /opt/venv /opt/venv

FROM runtime AS dev
COPY --from=dev-dependencies /opt/venv /opt/venv

# Локальный Compose монтирует src непосредственно в этот каталог.
FROM dev AS development-env
WORKDIR /opt/financial_manager
