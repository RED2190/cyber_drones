.PHONY: help prepare unit-test integration-test integration-test-run tests docker-up docker-down docker-logs docker-clean

PIPENV_PIPFILE = ../../config/Pipfile
PYTEST_CONFIG = ../../config/pyproject.toml
GENERATED = .generated
DOCKER_COMPOSE = docker compose -f $(GENERATED)/docker-compose.yml --env-file $(GENERATED)/.env

help:
	@echo "make prepare           - Собрать docker-compose + .env из компонентов"
	@echo "make docker-up         - Запустить систему (prepare + docker compose up)"
	@echo "make docker-down       - Остановить систему"
	@echo "make docker-logs       - Логи"
	@echo "make docker-clean      - Очистка docker ресурсов системы"
	@echo "make unit-test         - Проверка импортов/синтаксиса компонентов DronePort"
	@echo "make integration-test  - Smoke интеграция (подъём DronePort-стека)"
	@echo "make integration-test-run - Запустить integration pytest для DronePort"
	@echo "make tests             - Все тесты"

prepare:
	@cd ../.. && PIPENV_PIPFILE=config/Pipfile pipenv run python scripts/prepare_system.py systems/drone_port

docker-up: prepare
	@set -a && . $(GENERATED)/.env && set +a && \
		$(DOCKER_COMPOSE) --profile $${BROKER_TYPE:-mqtt} up -d --build

docker-down:
	-$(DOCKER_COMPOSE) --profile kafka down 2>/dev/null
	-$(DOCKER_COMPOSE) --profile mqtt down 2>/dev/null

docker-logs:
	@set -a && . $(GENERATED)/.env && set +a && \
		$(DOCKER_COMPOSE) --profile $${BROKER_TYPE:-mqtt} logs -f

docker-clean:
	-$(DOCKER_COMPOSE) --profile kafka down -v --rmi local 2>/dev/null
	-$(DOCKER_COMPOSE) --profile mqtt down -v --rmi local 2>/dev/null

unit-test:
	@PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run python -m compileall src -q

integration-test: docker-up
	@$(MAKE) integration-test-run
	-$(MAKE) docker-down

integration-test-run:
	@set -a && . $(GENERATED)/.env && set +a && \
		PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run pytest -c $(PYTEST_CONFIG) \
		systems/drone_port/tests/ \
		-v

tests: unit-test integration-test
