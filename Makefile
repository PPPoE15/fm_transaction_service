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
	docker-compose -f docker/docker-compose.yml -p financial_manager build --no-cache

gen_docker_env: ## Сгенерировать/обновить env-файл для запуска в docker
	$(MAKE) -C docker gen_docker_env

up_all:  ## Запуск сервиса.
	docker-compose -f docker/docker-compose.yml -p financial_manager up --force-recreate -d web #jobs scheduler

down_all:  ## Остановка сервиса.
	docker-compose -f docker/docker-compose.yml -p financial_manager down

migrate: ## Применить миграции для указанной в env файле БД.
	$(MAKE) -C src migrate

generate_migration:  ## Сгенерировать миграцию
	$(MAKE) -C src generate_migration

gen_dev_requirements: ## Сгенерировать файл requirements.txt для разработки
	$(MAKE) -C docker/modules gen_dev_requirements

install_dev_requirements: ## Установить все зависимости для разработки
	$(MAKE) gen_dev_requirements
	pip-sync
