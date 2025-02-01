#!/bin/bash

echo "Cleaning up..."
rm -f dev.env

crp=python-pip-uvicorn
crd=dramatiq-up
crs=scheduler-up

for cr in "${crp}" "${crd}" "${crs}";
do
    docker logs "${cr}" || true
    docker stop "${cr}" || true
    docker rm "${cr}" || true
done

docker rmi "$artifactory_docker"/"$python_image_to_run" || true
