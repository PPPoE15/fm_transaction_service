#!/bin/bash

set -eu

url_to_repo_for_apt=$(echo "$artifactory_deb_pkg_url" | awk -F '/pool' '{print $1}')

dpkg-buildpackage -us -uc -b

echo "-----------------------------------"
echo "Checking for the deb package"
echo "-----------------------------------"
ls ../"$debian_pkg_name"
result=$?
if [[ $result -eq 0 ]]
then
    echo "-------------------------------------"
    echo "Result successful, deb package found!"
    echo "-------------------------------------"
    max_iteration=5
    hashsum_sha256=$(openssl dgst -sha256 ../$debian_pkg_name |sed 's/^SHA256.*= //')
    hashsum_sha1=$(openssl dgst -sha1 ../$debian_pkg_name |sed 's/^SHA.*= //')
    hashsum_md5=$(md5sum ../$debian_pkg_name | awk '{print $1}')
    set +e
    echo "curl -v -u$username:$password"
    curl -v -u"$username":"$password" \
      -H "X-Checksum-Sha256:${hashsum_sha256}" \
      -H "X-Checksum-Sha1:${hashsum_sha1}" \
      -H "X-Checksum-Md5:${hashsum_md5}" \
      -XPUT \
      "$artifactory_deb_pkg_url/$branch/$debian_pkg_name;deb.distribution=$branch;deb.component=$component;deb.architecture=$architecture" -T ../"$debian_pkg_name" 2>&1 | tee curl.tmp

    lcur=$(grep -w completely curl.tmp)
    if [[ "$lcur" == *"We are completely uploaded and fine"* ]]
    then
        echo "----------------------------------------"
        echo "All curl requests were successful!"
        echo "----------------------------------------"
    else
        echo "-----------------------------------"
        echo "Curl is failed!!!"
        echo "-----------------------------------"
        exit 2
    fi
    echo "-----------------------------------------"
    echo "Verify the package uploaded to repository:"
    echo "-----------------------------------------"
    echo "deb $url_to_repo_for_apt $branch $component" >> /etc/apt/sources.list

    for i in $(seq 1 $max_iteration)
    do
      set +e
      apt-get clean && apt-get update && apt-get -d -y install "$debian_pkg_name_with_no_version=$debian_pkg_version"
      result=$?
      if [[ $result -eq 0 ]]
      then
          echo "-----------------------------------"
          echo "Result successful"
          echo "-----------------------------------"
          break
      else
          echo "-----------------------------------"
          echo "Result unsuccessful"
          echo "-----------------------------------"
          sleep 10
      fi
    done
    set -e
    if [[ $result -ne 0 ]]
    then
        echo "-----------------------------------"
        echo "All of the trials failed!!!"
        echo "-----------------------------------"
        exit 2
    fi
else
    echo "-----------------------------------"
    echo -e "There is no such deb_package \nor the name does not match"
    echo "-----------------------------------"
    exit 2
fi
