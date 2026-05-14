.PHONY: help prepare unit-test test-all-docker tests docker-up docker-down docker-logs

PIPENV_PIPFILE = ../../config/Pipfile
PYTEST_CONFIG  = ../../config/pyproject.toml
GENERATED      = .generated
DOCKER_COMPOSE = docker compose -f $(GENERATED)/docker-compose.yml --env-file $(GENERATED)/.env

help:
	@echo "make prepare           - Собрать docker-compose + .env из компонентов"
	@echo "make docker-up         - Запустить систему (prepare + docker compose up)"
	@echo "make docker-down       - Остановить систему"
	@echo "make docker-logs       - Логи"
	@echo "make unit-test         - Unit тесты"
	@echo "make test-all-docker   - Интеграционные тесты с docker"
	@echo "make tests             - Все тесты"

prepare:
	@cd ../.. && PIPENV_PIPFILE=config/Pipfile pipenv run python scripts/prepare_system.py systems/alt_insurer

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
		$(DOCKER_COMPOSE) $$profiles logs -f

unit-test:
	@PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run pytest -c $(PYTEST_CONFIG) tests/unit/ -v

test-all-docker: docker-up
	@echo "Waiting for broker and components..."
	@sleep 45
	@set -a && . $(GENERATED)/.env && set +a && \
		PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run pytest -c $(PYTEST_CONFIG) tests/integration/ -v
	-$(MAKE) docker-down

tests: unit-test test-all-docker
