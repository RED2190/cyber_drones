.PHONY: help prepare unit-test test-all-docker tests docker-up docker-down docker-logs

PROJECT_ROOT ?= ../..
PIPENV_PIPFILE = $(PROJECT_ROOT)/config/Pipfile
PYTEST_CONFIG = $(PROJECT_ROOT)/config/pyproject.toml
GENERATED = .generated
DOCKER_COMPOSE = docker compose -f $(GENERATED)/docker-compose.yml --env-file $(GENERATED)/.env

help:
	@echo "make prepare           - Собрать docker-compose + .env из компонентов"
	@echo "make docker-up         - Запустить систему (prepare + docker compose up)"
	@echo "make docker-down       - Остановить систему"
	@echo "make docker-logs       - Логи"
	@echo "make unit-test         - Unit тесты компонентов"
	@echo "make test-all-docker   - Интеграционные тесты c использованием docker (docker required)"
	@echo "make tests             - Все тесты"

prepare:
	@cd $(PROJECT_ROOT) && PIPENV_PIPFILE=config/Pipfile pipenv run python scripts/prepare_system.py systems/operator

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
	@PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run pytest -c $(PYTEST_CONFIG) tests/test_unit.py -v

test-all-docker:
	@echo "No integration tests yet (stubs)."

tests: unit-test

