set -eux

for container in "python-pip"; do
  docker stop "$container" || true ; docker rm "$container" || true;
done

docker rmi -f "$artifactory_docker"/"$python_pip_image" "$artifactory_docker"/"$python_pip_req_services" || true
