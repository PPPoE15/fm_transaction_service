migrate: ## Применить миграции для указанной в env файле БД.
	alembic upgrade head

generate_migration:  ## Сгенерировать миграцию
	@read -p "Migration title: " migration_title; \
	alembic revision --autogenerate -m "$$migration_title"
