.PHONY: help prepare unit-test integration-test test-all-docker tests docker-up docker-down docker-logs

PROJECT_ROOT ?= ../..
PIPENV_PIPFILE = $(PROJECT_ROOT)/config/Pipfile
PYTEST_CONFIG = $(PROJECT_ROOT)/config/pyproject.toml
GENERATED = .generated
DOCKER_COMPOSE = docker compose -f $(GENERATED)/docker-compose.yml --env-file $(GENERATED)/.env

help:
	@echo "make prepare           - Собрать docker-compose + .env"
	@echo "make docker-up         - Запустить систему"
	@echo "make docker-down       - Остановить"
	@echo "make unit-test         - Юнит тесты"
	@echo "make integration-test  - Интеграционные тесты"
	@echo "make test-all-docker   - Все тесты (unit + integration)"

prepare:
	@cd $(PROJECT_ROOT) && PIPENV_PIPFILE=config/Pipfile pipenv run python scripts/prepare_system.py systems/regulator

docker-up: prepare
	@set -a && . $(GENERATED)/.env && set +a && \
		profiles="--profile $${BROKER_TYPE:-kafka}"; \
		$(DOCKER_COMPOSE) $$profiles up -d --build

docker-down:
	@set -a && . $(GENERATED)/.env && set +a && \
		profiles="--profile $${BROKER_TYPE:-kafka}"; \
		$(DOCKER_COMPOSE) $$profiles down 2>/dev/null || true

docker-logs:
	@set -a && . $(GENERATED)/.env && set +a && \
		profiles="--profile $${BROKER_TYPE:-kafka}"; \
		$(DOCKER_COMPOSE) $$profiles logs -f

unit-test:
	@PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run pytest -c $(PYTEST_CONFIG) \
		tests/test_certificate_manager.py \
		tests/test_config.py \
		tests/test_dispatcher.py \
		tests/test_handlers.py \
		-v 2>/dev/null || true

integration-test: docker-up
	@echo "Running integration tests..."
	@set -a && . $(GENERATED)/.env && set +a && \
		PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run pytest -c $(PYTEST_CONFIG) \
		tests/test_integration.py -v; \
		EXIT_CODE=$$?; \
		$(MAKE) docker-down; \
		exit $$EXIT_CODE

test-all-docker: unit-test integration-test

tests: unit-test