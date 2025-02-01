set -euo pipefail

if [[ -n "${shortPlanBranchName}" ]];
then
  shortPlanBranchName=$(echo "${shortPlanBranchName}" | tr '[:upper:]' '[:lower:]')
  echo "Branch name is $shortPlanBranchName ..."
else
  echo "It seems shortPlanBranchName var is empty, so considering this as the default plan branch name..."
  shortPlanBranchName=master
fi


if [[ ${shortPlanBranchName} == "master" ]] || [[ ${shortPlanBranchName} == "rc" ]] || [[ ${shortPlanBranchName} == "release" ]] \
      ||
   [[ "${sourceBranch}" == "feature/"* && "${targetBranch}" == "master" ]] \
      || \
   [[ "${sourceBranch}" == "feature/"* && "${targetBranch}" == "dev" ]] \
      || \
   [[ "${sourceBranch}" == "bugfix/"* && "${targetBranch}" == "master" ]] \
      || \
   [[ "${sourceBranch}" == "bugfix/"* && "${targetBranch}" == "dev" ]];
then
  echo "Docker login $artifactory_docker repo..."
  docker login --username "${username}" --password "${password}" "${artifactory_docker}"

  docker tag "${artifactory_docker}"/"${python_image_to_run}" "${artifactory_docker}"/"${shortPlanName}-${shortPlanBranchName}":latest

  echo "Docker push to ${artifactory_docker}..."
  docker push "${artifactory_docker}"/"${shortPlanName}-${shortPlanBranchName}":latest

  echo "Docker logout from ${artifactory_docker}..."
  docker logout ${artifactory_docker}
fi


if [[ ${shortPlanBranchName} == "master" ]] || [[ ${shortPlanBranchName} == "rc" ]] || [[ ${shortPlanBranchName} == "release" ]];
then

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

  cat yc_astra_sa_key.json | docker login --username json_key --password-stdin cr.yandex

  echo "Docker push to YC..."
  docker tag "${artifactory_docker}"/"${shortPlanName}-${shortPlanBranchName}":latest "${yandex_url_docker}"/"${yandex_registry_id}"/"${shortPlanName}-${shortPlanBranchName}":latest
  docker push "${yandex_url_docker}"/"${yandex_registry_id}"/"${shortPlanName}-${shortPlanBranchName}":latest

  echo "Docker logout from YC"
  docker logout "${yandex_url_docker}"
fi
