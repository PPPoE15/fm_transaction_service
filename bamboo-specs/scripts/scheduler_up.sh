#!/bin/bash
set -eu
export PYTHONPATH=src

source .ci_env && envsubst < template.env > "${PYTHONPATH}"/dev.env
cd $PYTHONPATH
python3 -m modules.jobs.scheduler
