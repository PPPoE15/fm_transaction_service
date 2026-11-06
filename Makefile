run_linters: ## Запуск линтеров
	ruff check src --fix || echo
	ruff format src --check || echo
	mypy src || echo

# Историческое имя сохранено; изолированный Postgres поднимает testcontainers.
test_downgrade_migrations_compose:  ## Проверить upgrade/downgrade на отдельном Docker Postgres.
	poetry run pytest src/tests/test_migrations.py src/tests/modules/transaction/test_version_migration.py src/tests/modules/transaction/test_index_migration.py

pytest_coverage:  ## Запуск pytest с coverage
	pytest --cov --cov-report html

build: ## Собрать образ.
	COMPOSE_DOCKER_CLI_BUILD=1 DOCKER_BUILDKIT=1 docker-compose -f docker/docker-compose.yml -p financial_manager build --no-cache

up_all:  ## Запуск сервиса.
	docker-compose -f docker/docker-compose.yml -p financial_manager up --force-recreate -d web

down_all:  ## Остановка сервиса.
	docker-compose -f docker/docker-compose.yml -p financial_manager down

migrate: ## Применить миграции для указанной в env файле БД.
	$(MAKE) -C src migrate

generate_migration:  ## Сгенерировать миграцию
	$(MAKE) -C src generate_migration

venv:
	rm -rf .venv venv
	python3 -m venv .venv
	.venv/bin/pip install poetry==2.1
	.venv/bin/poetry install --all-groups

build_dev:
	docker build --target dev -t pppoe15/fm_transaction_service:dev .

push_dev:	
	docker login
	docker push pppoe15/fm_transaction_service:dev
