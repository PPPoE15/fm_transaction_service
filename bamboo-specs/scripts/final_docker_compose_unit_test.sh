if [[ -n "${shortPlanBranchName}" ]];
then
shortPlanBranchName=$(echo "${shortPlanBranchName}" | tr '[:upper:]' '[:lower:]')
  echo "Branch name is $shortPlanBranchName..."
else
  echo "It seems shortPlanBranchName var is empty, so considering this as the default plan branch name..."
  shortPlanBranchName=master
fi

if [[ "${sourceBranch}" == "feature/"* && "${targetBranch}" == "master" ]] \
      || \
   [[ "${sourceBranch}" == "feature/"* && "${targetBranch}" == "dev" ]] \
      || \
   [[ "${sourceBranch}" == "bugfix/"* && "${targetBranch}" == "master" ]] \
      || \
   [[ "${sourceBranch}" == "bugfix/"* && "${targetBranch}" == "dev" ]];
then

  echo "Show docker compose services status..."
  docker-compose -f "$docker_compose_file" ps -a

  echo "Show docker compose logs if status unhealthy found or show unit-test-service logs..."
  docker inspect --format "{{json .State.Health.Status }}" $(docker-compose -f "$docker_compose_file" ps -qa ) | grep unhealthy \
    && docker-compose -f "$docker_compose_file" logs \
    || docker-compose -f "$docker_compose_file" logs unit-test-service

  echo "Show docker compose logs if some of the containers is marked as Exited..."
  docker-compose -f "$docker_compose_file" ps -a | grep -q "Exited (0)" || docker-compose -f "$docker_compose_file" logs

  echo "Show docker inspect output..."
  docker inspect --format "{{json .State.Health }}" $(docker-compose -f "$docker_compose_file" ps -qa ) | jq .

  echo "Cleaning up docker compose..."
  docker-compose -f "$docker_compose_file" rm -svf

  echo "Cleaning docker image ${artifactory_docker_common_url}/${shortPlanName}-${shortPlanBranchName}..."
  curl -u "${username}":"${password}" -X DELETE "${artifactory_docker_common_url}/${shortPlanName}-${shortPlanBranchName}/latest"
  curl -u "${username}":"${password}" -X DELETE "${artifactory_docker_common_url}/${shortPlanName}-${shortPlanBranchName}"

  echo "Cleaning docker image "

  echo "Docker login to YC..."
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


else

  echo "It seems there is no need to run it in this case..."

fi
