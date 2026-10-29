# Образы transaction-service (FM-67)

Сборка из корня репозитория:

```sh
docker build --platform linux/arm64 --target dev -t fm-transaction:dev .
docker build --platform linux/arm64 --target master -t fm-transaction:master .
docker build --platform linux/arm64 -f docker/Dockerfile --target development-env -t financial_manager:testing .
docker run --rm fm-transaction:dev python scripts/check-image.py dev
docker run --rm fm-transaction:master python scripts/check-image.py master
```

Для amd64 замените `--platform` на `linux/amd64`. CI проверяет amd64.
Локальный Compose по-прежнему: `docker compose -f docker/docker-compose.yml`.
Ключ JWT нужно смонтировать согласно примечанию в Compose.

`master` содержит только common-зависимости; `dev` дополнительно содержит
pytest, mypy, ruff и debugpy. Poetry устанавливает зависимости в builder,
не попадая в runtime. Компиляторы для текущих wheels не требуются. Если будущая
зависимость потребует сборки, инструменты устанавливаются только в builder.
`docker/Dockerfile` совпадает с основным, кроме последней стадии default:
master в корне, development-env в docker/. Изменяйте общий текст обоих файлов;
CI проверяет совпадение и отдельно строит оба варианта без --target.

## Сравнение на linux/arm64

Дата: 2026-10-29. Исходный код: `423de8bc8d6930ec4e6ef2a62a7cf13f244be513`.
Docker Engine 29.6.1, containerd image store. Измерение одним способом:

```sh
docker image inspect fm-67-transaction-before:dev fm-67-transaction-before:master \
  fm-67-transaction-after:dev fm-67-transaction-after:master \
  --format '{{.RepoTags}} {{.Architecture}} {{.Size}}'
```

| Цель | До, байт | После, байт | Уменьшение |
|---|---:|---:|---:|
| dev | 543001989 | 99835329 | 81,61% |
| master | 478192078 | 66364492 | 86,12% |

Это значение Size данного Docker storage backend, а не сумма распакованных слоёв
и не уникальное место на диске; сравнивать его напрямую с 2,1 ГБ из issue нельзя.
Для исходных образов использован прежний Dockerfile с теми же lock-файлом и
архитектурой, команды сборки те же с тегом before. Для исходной master-сборки
в scripts уже находился новый проверочный скрипт (около 1,5 КБ).

Базы (digest manifest list, зафиксирован журналом сборки):
- До: `python:3.13-bookworm@sha256:3856e3e7bf4d0ba061501a84ed2eb0d429663307c0f54f191dc4de03c7081c3e`.
- После: `python:3.13-slim-bookworm@sha256:281d39ff02e3b389401586134ff9e6572954687822a58055ec07a60ded4e0b7f`.

`PYTHON_IMAGE` позволяет передать digest через `--build-arg` для повторения.

Обе базы предоставляют Python 3.13.18. Основные оставшиеся слои по
`docker image history --no-trunc` (распакованные, не складывать с Size выше):
Debian — 108 MB, Python — 44,8 MB, базовые системные пакеты — 9,67 MB,
curl/gettext/tzdata — 6,75 MB, venv — 242 MB в dev и 77,2 MB в master.
Код — около 1,21 MB. Общие слои Docker хранит совместно.

Проверено: все три цели собираются; `check-image.py` проходит, debugpy 1.8.17
доступен в development-env. На отдельном Compose-проекте с новой БД, своими
JWT-ключами и исходной конфигурацией `fm_devops/docker-compose.yaml` прошли
миграции обоих сервисов, регистрация/вход, отказ без JWT и создание/чтение
транзакции. Контрольный auth — существующий `pppoe15/fm_auth_service:dev`.
Порты smoke-проекта: 18082/18083, volume БД отдельный; исходный стенд не менялся.
Оптимизация auth и итоговая проверка всей задачи #67 остаются отдельной частью.

Smoke повторён также с `master`: тот же сценарий прошёл. Образы замера:
- before/dev: `sha256:cc53a52331efe02ce3eefe1893bf2be4003720fbe1e019800ae77e303839bdab`;
- before/master: `sha256:d94f27376a43d4cc427af0181fcb806f423480368cb1dd2fe0000a93679ee0a0`;
- after/dev: `sha256:aeafa724900bb3fb52321c1dc539b48b985af53357a51373f3d5eaf8186e9c29`;
- after/master: `sha256:5bb52f6003d8c30271ba63b627222edf8cfe977330ba33fef26b8ca85cce1260`.
Замер сделан до обновления текстового ожидания CI в `test_publication.py`;
зависимости и Dockerfile после замера не менялись.
