#!/bin/bash

set -eux

echo "Upgrade pip"
python3 -m pip install --upgrade pip

# cd to a temp dir created in the current
cd $(mktemp -d -p $(pwd))

echo "Search packages in artifactory"
# run in parallel as it takes a while to go through the loop
grep -v "#\|^$\|^--extra-index-url" ../requirements.txt | xargs -I{} -P30 sh -c \
  'line={}; python3 -m pip install --dry-run \
   -i https://artifactory.astralinux.ru/artifactory/api/pypi/acmp-pypi-packages/simple \
   --no-deps \
   "$line" || echo "${line}" >> requirements-to-add.txt'

if [ -f requirements-to-add.txt ]; then
        echo "$(wc -l requirements-to-add.txt | cut -d' ' -f1) package(s) will be added to artifactory"

        echo "Install python packages"
        python3 -m pip install safety twine

        echo "Check packages with Safety"
        python3 -m safety check -r requirements-to-add.txt

        echo "Download missed packages from PyPI"
        python3 -m pip download --no-deps -r requirements-to-add.txt

        if ls *.tar.gz &>/dev/null; then
                echo "$(ls -l *.tar.gz | wc -l) package(s) will be built from sources"

                echo "Install python build dependencies"
                apt-get update
                apt-get install -y python$(python3 --version | grep -Po '(?<=Python )[0-9]*\.[0-9]*(?=\.[0-9])' )-dev gcc

                echo "Install python build library"
                python3 -m pip install build

                echo "Make wheel from sources"
                python3 -m pip wheel *.tar.gz
        fi

        echo "Upload missed packages to artifactory"
        pypi_upload_url="$artifactory_pypi_url"
        echo -e "[distutils]\nindex-servers = local\n[local]\nrepository: ${pypi_upload_url%/*}\nusername: $secret_username\npassword: $secret_password" > .pypirc
        twine upload -r local *.whl --config-file .pypirc

        echo "Clean up"
        rm -f .pypirc
else
        echo "PyPi repo is up to date, nothing to do"
fi
