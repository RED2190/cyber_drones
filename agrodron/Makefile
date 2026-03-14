.PHONY: help prepare check-tools check-docker unit-test integration-test tests docker-up docker-down docker-logs

PIPENV_PIPFILE = ../config/Pipfile
PYTEST_CONFIG = ../config/pyproject.toml
GENERATED = .generated
DOCKER_COMPOSE = docker compose -f $(GENERATED)/docker-compose.yml --env-file $(GENERATED)/.env

help:
	@echo "make prepare           - Собрать docker-compose + .env из компонентов"
	@echo "make check-tools       - Проверить pipenv/pytest"
	@echo "make check-docker      - Проверить доступ к Docker daemon"
	@echo "make docker-up         - Запустить систему (prepare + docker compose up)"
	@echo "make docker-down       - Остановить систему"
	@echo "make docker-logs       - Логи"
	@echo "make unit-test         - Unit тесты компонентов"
	@echo "make integration-test  - Интеграционные тесты (docker required)"
	@echo "make tests             - Все тесты"

prepare:
	@cd .. && PIPENV_PIPFILE=config/Pipfile pipenv run python scripts/prepare_system.py agrodron

check-tools:
	@command -v pipenv >/dev/null 2>&1 || (echo "pipenv not found. Run: make init (repo root)"; exit 1)
	@PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run python -m pytest --version >/dev/null 2>&1 || \
		(echo "pytest not available in Pipenv. Run: PIPENV_PIPFILE=config/Pipfile pipenv install --dev pytest"; exit 1)

check-docker:
	@docker ps >/dev/null 2>&1 || (echo "Docker daemon unavailable. Check docker group or run with sudo."; exit 1)

docker-up: prepare
	@set -a && . $(GENERATED)/.env && set +a && \
		$(DOCKER_COMPOSE) --profile $${BROKER_TYPE:-kafka} up -d --build

docker-down:
	-$(DOCKER_COMPOSE) --profile kafka down 2>/dev/null
	-$(DOCKER_COMPOSE) --profile mqtt down 2>/dev/null

docker-logs:
	@set -a && . $(GENERATED)/.env && set +a && \
		$(DOCKER_COMPOSE) --profile $${BROKER_TYPE:-kafka} logs -f

unit-test: check-tools
	@PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run pytest -c $(PYTEST_CONFIG) src -vv -rA -s

integration-test: check-tools check-docker docker-up
	@echo "Waiting for broker and components..."
	@sleep 45
	@set -a && . $(GENERATED)/.env && set +a && \
		PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run pytest -c $(PYTEST_CONFIG) tests/test_integration.py -vv -rA -s
	-$(MAKE) docker-down

tests: unit-test integration-test
