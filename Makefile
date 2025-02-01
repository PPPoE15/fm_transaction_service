run_linters: ## Запуск линтеров
	ruff src --no-cache || echo
	mypy --cache-dir=/dev/null src || echo

test_downgrade_migrations_compose:  ## Запуск проверки отката всех миграций через docker compose.
	docker compose -f docker/docker-compose-dev-team.yaml -p python-template-tests up --force-recreate --abort-on-container-exit downgrade-migrations-tests || true
	docker compose -f docker/docker-compose-dev-team.yaml -p python-template-tests down -v --remove-orphans

pytest_coverage:  ## Запуск pytest с coverage
	pytest --cov --cov-report html

build: ## Собрать образ.
	docker compose -f docker/docker-compose.yml -p python-template build

up_all:  ## Запуск сервиса.
	docker compose -f docker/docker-compose.yml -p python-template up --force-recreate -d web jobs scheduler

down_all:  ## Остановка сервиса.
	docker compose -f docker/docker-compose.yml -p python-template down

migrate: ## Применить миграции для указанной в env файле БД.
	alembic upgrade head

generate_migration:  ## Сгенерировать миграцию
	@read -p "Migration title: " migration_title; \
	alembic revision --autogenerate -m "$$migration_title"

gen_dev_requirements: ## Сгенерировать файл requirements.txt для разработки
	$(MAKE) -C docker/modules gen_dev_requirements

install_dev_requirements: ## Установить все зависимости для разработки
	$(MAKE) gen_dev_requirements
	pip-sync
