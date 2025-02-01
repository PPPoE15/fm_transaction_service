#!/bin/bash
set -eu
export dramatiq_prom_host="0.0.0.0"
export dramatiq_prom_port=9191
export PYTHONPATH=src

source .ci_env && envsubst < template.env > ${PYTHONPATH}/dev.env
cd $PYTHONPATH
dramatiq -p 1 modules.jobs.main
