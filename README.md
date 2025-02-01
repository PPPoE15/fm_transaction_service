# Шаблон для python проекта

Данный проект создан как заготовка для старта python проектов.

## Требования к ОС для развертывания

В ОС должен быть установлен пакет:
```
sudo apt-get install python3-venv
```
В корень проекта (на уровне с директорий app) необходимо добавить файл dev.env или prod.env. Переменные, указанные в файле prod.env имеют приоритет над переменными в файле dev.env. Переменные среды имеют приоритет над переменными файлов dev.env и prod.env
Помимо dev.env и/или prod.env в ОС должна быть директория ```/run/secrets```, в которой в виде файлов хранятся пароли/ключи (имена файлов учитывают регистр). Минимальным набором является два файла:
 - файл POSTGRES_PASSWORD для хранения пароля доступа к PostgreSQL;
 - файл SECRET_KEY для работы с JWT;
 - файл RABBITMQ_PASSWORD для хранения пароля доступа к RabbitMQ.


### Виртуальная среда

Для старта проекта необходимо создать в корне директорию виртуальной среды
```
user@netid:~/path/to/project$ python3 -m venv env
```
Либо если виртуальная среда создается на корпоративной машине
```
user@netid:~/path/to/project$ python3.8 -m venv env
```
После создания виртуальной среды и ее активации необходимо установить пакет pip-tools, установить зависимости
```
(env) user@netid:~/path/to/project$ pip install pip-tools
(env) user@netid:~/path/to/project$ pip-compile --resolver=backtracking
(env) user@netid:~/path/to/project$ pip-sync
```
Установить все hook'и для pre-commit
```
(env) user@netid:~/path/to/project$ pre-commit install
```

### Статический анализ

В корне проекта находятся конфигурационные файлы. Файлы требуются для исключения из списка тестируемых отдельных сообщений типа error, warning и т.д. Но в определенных случаях требуется исключить из проверки ту или иную строку. 

***Исключение из проверки Pylint***
```
from .item import Item  # pylint: disable=import-error
```

***Исключение из проверки Bandit***
```
def random_lower_string() -> str:
    return "".join(random.choices(string.ascii_lowercase, k=32))  # nosec
```

***Исключение из проверки Flake8***
```
# flake8: noqa
from .item import Item
```

***Исключение из проверки mypy***
```
def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:  # type: ignore
```

### Инструкция к наполнению requirements

1. В requirements-service.in содержатся только тяжелые и не требующие постоянного изменения зависимости, которые в последующем будут использованны в bamboo
(к примеру alembic и asyncpg)  

2. В requirements.in содержатся все зависимости(включая тех, которые требуют постоянных изменений, например pika и fastapi)  

### Manual execution guide

Make sure the current directory is changed to the directory of this GIT repo

For example: `cd /opt/astra/bitbucket/python-template`

Pull the nginx-unit docker image (currently the latest build tag is ***v1.29.1_5***)
from Artifactory(requires VPN):  
`docker pull acmp-docker.artifactory.astralinux.ru/nginx-unit:v1.29.1_5`
or YC (requires SSO):  
`docker pull cr.yandex/crpg6vo83nrq909nf3d6/nginx-unit:v1.29.1_5`

#### First approach (interactive)
Run the docker image with creation interactive bash shell in the container:  
```
docker run --rm -it --name nginx-unit \
    -v `pwd`/nginx-unit:/docker-entrypoint.d  \
    -v `pwd`:/work -v `pwd`:/srv/python-template \
    -w /work -p 80:80 acmp-docker.artifactory.astralinux.ru/nginx-unit:v1.29.1_5 bash
```
Run the following script or execute line by line for better debugging:  
```
cp -pr template.env dev.env &&\
apt-get update && apt-get install -y python3.7-dev gcc &&\
python3 -m pip install --upgrade pip &&\
pip3 install -r /work/requirements.txt &&\
unitd &&\
mkdir -p /run/secrets &&\
echo "password" >> /run/secrets/POSTGRES_PASSWORD &&\
echo "secret_key" >> /run/secrets/SECRET_KEY &&\
curl -X PUT --data-binary @/docker-entrypoint.d/config.json  --unix-socket /var/run/control.unit.sock http://localhost/config &&\
curl http:/127.0.0.1/api/v1/ping
```

#### Second approach (detached)
Go to nginx-unit/preconfigure.sh and uncomment all commented lines  
Run the docker image detached  
```
docker run -d --name nginx-unit \
    -v `pwd`/nginx-unit:/docker-entrypoint.d  \
    -v `pwd`:/work -v `pwd`:/srv/python-template \
    -w /work -p 80:80  acmp-docker.artifactory.astralinux.ru/nginx-unit:v1.29.1_5
```
Verify logs:  
`docker logs -f nginx-unit`

Curl it:  
`curl -X GET http:/127.0.0.1/api/v1/ping`

Checkout changed preconfigure.sh:  
`git checkout nginx-unit/preconfigure.sh`

### PiPy repository
All python libraries mentioned in requirements.txt will be added to the [PyPi artifactory repo](https://artifactory.astralinux.ru/ui/repos/tree/General/acmp-pypi-packages)
