set -eu

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

  nohup dockerd > /dev/null 2>&1 &
  # let docker daemon to warm up a bit
  sleep 10

  # specify .ci_unit_env first, so that it has a priority over .ci_env file
  source <(cat .ci_unit_env .ci_env) && envsubst < template.env > dev.env

  echo "Running Unit Tests..."
  docker-compose --env-file ./dev.env -f "$docker_compose_file" up -d --build --remove-orphans --force-recreate

else

  echo "It seems there is no need to run unit tests in this case..."

fi
