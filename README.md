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


