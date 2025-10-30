run_linters: ## Запуск линтеров
	ruff check src || echo
	ruff format src --check || echo
	mypy src || echo

test_downgrade_migrations_compose:  ## Запуск проверки отката всех миграций через docker compose.
	docker compose -f docker/docker-compose-dev-team.yaml -p financial_manager-tests up --force-recreate --abort-on-container-exit downgrade-migrations-tests || true
	docker compose -f docker/docker-compose-dev-team.yaml -p financial_manager-tests down -v --remove-orphans

pytest_coverage:  ## Запуск pytest с coverage
	pytest --cov --cov-report html

build: ## Собрать образ.
	COMPOSE_DOCKER_CLI_BUILD=1 DOCKER_BUILDKIT=1 docker-compose -f docker/docker-compose.yml -p financial_manager build --no-cache

gen_docker_env: ## Сгенерировать/обновить env-файл для запуска в docker
	$(MAKE) -C docker gen_docker_env

up_all:  ## Запуск сервиса.
	docker-compose -f docker/docker-compose.yml -p financial_manager up --force-recreate -d web

down_all:  ## Остановка сервиса.
	docker-compose -f docker/docker-compose.yml -p financial_manager down

migrate: ## Применить миграции для указанной в env файле БД.
	$(MAKE) -C src migrate

generate_migration:  ## Сгенерировать миграцию
	$(MAKE) -C src generate_migration

install_poetry: ## Установить poetry
	pip install poetry==2.1
	poetry self add poetry-plugin-export

gen_requirements: ## Сгенерировать/обновить файлы requirements.txt
	poetry export --only dev --without-hashes --format requirements.txt --output requirements-ci.txt
	poetry export --only common --without-hashes --format requirements.txt --output requirements.txt

venv:
	rm -rf .venv venv
	python3 -m venv .venv
	.venv/bin/pip install poetry==2.1
	.venv/bin/poetry install --all-groups
