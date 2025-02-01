#!/bin/bash

set -euxo pipefail

# Declare HOME var to prevent docker from WARNINGs
export HOME=/root
df -h

requirements_file="requirements.txt"
requirements_hash=$(md5sum ./"$requirements_file" | awk '{ print $1 }')

# Checking the presence of a base image in the remote registry and obtaining its hash
echo "Checking remote base image..."
base_image_manifest=$(docker manifest inspect "$artifactory_docker/$python_pip_image")
base_image_version=$(echo "$base_image_manifest" | grep -oP '"digest":\s*"\K[^"]+' | head -n 1)

cat <<EOF > Dockerfile
FROM "$artifactory_docker"/"$python_pip_image"
ENV TERM xterm-256color
ENV DEBIAN_FRONTEND noninteractive
LABEL base_image_version="${base_image_version}"
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir --upgrade pip \
&& pip3 install --no-cache-dir --timeout=120 -r requirements.txt
EOF

cat > yc_astra_sa_key.json <<EOF
{
   "id": "ajem619sr6ii69lqsbna",
   "service_account_id": "aje0v89bicqf219hlj77",
   "created_at": "2023-03-21T13:22:00.666912372Z",
   "key_algorithm": "RSA_2048",
   "public_key": "${YCSApub}",
   "private_key": "${YCSApriv}"
}
EOF

docker_builder_pusher () {
  docker rmi "$artifactory_docker"/"$python_pip_req_services" || true
  docker build --network=host --no-cache=true \
    -t "$artifactory_docker"/"$python_pip_req_services" .
  docker login --username "$username" --password "$password" "$artifactory_docker"
  docker push "$artifactory_docker"/"$python_pip_req_services"
  docker logout "$artifactory_docker"

  echo "Docker login to YC..."
  cat yc_astra_sa_key.json | docker login --username json_key --password-stdin cr.yandex
  echo "Docker push to YC..."
  docker tag "$artifactory_docker"/"$python_pip_req_services" "$yandex_url_docker"/"$yandex_registry_id"/"$python_pip_req_services"
  docker push "$yandex_url_docker"/"$yandex_registry_id"/"$python_pip_req_services"
  echo "Docker logout from YC"
  docker logout "$yandex_url_docker"
}

dockerexists=$(docker manifest inspect "$artifactory_docker"/"$python_pip_req_services" || true)

if [ -n "$dockerexists" ]; then
  echo "Docker image exists already..."
  requirements_hash_in_docker=$(docker run --rm --name python-pip "$artifactory_docker"/"$python_pip_req_services" \
    md5sum "$requirements_file" | awk '{print $1}' || echo "")
  base_image_version_in_docker=$(docker inspect --format '{{ index .Config.Labels "base_image_version" }}' "$artifactory_docker/$python_pip_req_services" \
    || echo "")
  if [ "$requirements_hash" != "$requirements_hash_in_docker" ]; then
    echo "Changes detected in $requirements_file, triggering new build..."
    docker_builder_pusher
  elif [ "$base_image_version" != "$base_image_version_in_docker" ]; then
    echo "Changes detected in base image version, triggering new build..."
    docker_builder_pusher
  else
    echo "No changes detected in $requirements_file or base image version."
  fi
else
  echo "Docker image does not exist..."
  docker_builder_pusher
fi
