gen_dev_requirements: ## Сгенерировать файл requirements.txt для разработки
	pip-compile requirements-dev.in --resolver=backtracking --no-header -o ../../requirements.txt

gen_requirements: ## Сгенерировать файл requirements.txt для разработки
	pip-compile requirements-dev.in --resolver=backtracking --no-header -o ../../requirements.txt

gen_docker_env: ## Сгенерировать/обновить env-файл для запуска в docker
	dotenv -f .docker_env run envsubst < ../template.env > docker.env
