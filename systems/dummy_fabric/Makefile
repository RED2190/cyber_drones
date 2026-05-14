.PHONY: help prepare unit-test test-e2e test-all-docker tests docker-up docker-down docker-logs

PIPENV_PIPFILE = ../../config/Pipfile
PYTEST_CONFIG = ../../config/pyproject.toml
GENERATED = .generated
DOCKER_COMPOSE = docker compose -f $(GENERATED)/docker-compose.yml --env-file $(GENERATED)/.env

help:
	@echo "make prepare           - Собрать docker-compose + .env из компонентов"
	@echo "make docker-up         - Запустить систему (prepare + docker compose up)"
	@echo "make docker-down       - Остановить систему"
	@echo "make docker-logs       - Логи"
	@echo "make unit-test         - Unit тесты компонентов"
	@echo "make test-e2e          - E2E тесты (требуется Fabric + docker)"
	@echo "make test-all-docker   - E2E тесты c docker (docker required)"
	@echo "make tests             - Все тесты"

prepare:
	@cd ../.. && PIPENV_PIPFILE=config/Pipfile pipenv run python scripts/prepare_system.py systems/dummy_fabric

docker-up: prepare
	@set -a && . $(GENERATED)/.env && set +a && \
		profiles="--profile $${BROKER_TYPE:-kafka}"; \
		[ "$${ENABLE_ELK:-false}" = "true" ] && profiles="$$profiles --profile elk"; \
		[ "$${ENABLE_FABRIC:-false}" = "true" ] && profiles="$$profiles --profile fabric"; \
		$(DOCKER_COMPOSE) $$profiles up -d --build

docker-down:
	@set -a && . $(GENERATED)/.env && set +a && \
		profiles="--profile $${BROKER_TYPE:-kafka}"; \
		[ "$${ENABLE_ELK:-false}" = "true" ] && profiles="$$profiles --profile elk"; \
		[ "$${ENABLE_FABRIC:-false}" = "true" ] && profiles="$$profiles --profile fabric"; \
		$(DOCKER_COMPOSE) $$profiles down 2>/dev/null || true

docker-logs:
	@set -a && . $(GENERATED)/.env && set +a && \
		profiles="--profile $${BROKER_TYPE:-kafka}"; \
		[ "$${ENABLE_ELK:-false}" = "true" ] && profiles="$$profiles --profile elk"; \
		[ "$${ENABLE_FABRIC:-false}" = "true" ] && profiles="$$profiles --profile fabric"; \
		$(DOCKER_COMPOSE) $$profiles logs -f

unit-test:
	@PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run pytest -c $(PYTEST_CONFIG) tests/test_unit.py -v

test-e2e: docker-up
	@echo "Waiting for containers to initialize..."
	@sleep 10
	@set -a && . $(GENERATED)/.env && set +a && \
		PIPENV_PIPFILE=$(PIPENV_PIPFILE) FABRIC_PROXY_WAIT=120 \
		pipenv run pytest -c $(PYTEST_CONFIG) tests/test_e2e.py -v -rs
	-$(MAKE) docker-down

test-all-docker: test-e2e

tests: unit-test test-e2e
