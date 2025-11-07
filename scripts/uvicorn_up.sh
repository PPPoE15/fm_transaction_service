#!/bin/bash
set -e

SERVICE_NAME=$(basename "$PWD")
UVICORN_PORT=${UVICORN_PORT:-80}
ENV_FILE=${ENV_FILE:-dev.env}

# Create data directory
# mkdir -p "/opt/acm/$SERVICE_NAME-data"

# Generate env file
cp template.env ${ENV_FILE}

# Run app
START_CMD="uvicorn --host 0.0.0.0 --port ${UVICORN_PORT} src.main:app --log-level warning"
if [[ "$DEBUGPY_ENABLE" == "1" ]]; then
    START_CMD="debugpy --listen 0.0.0.0:5678 -m ${START_CMD} --reload"
fi
eval "${START_CMD}"