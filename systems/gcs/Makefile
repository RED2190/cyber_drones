.PHONY: help prepare unit-test unit-test-cov integration-test integration-test-no-up tests tests-no-up docker-up docker-up-no-broker docker-down docker-down-no-broker docker-logs

PIPENV_PIPFILE = ../../config/Pipfile
PYTEST_CONFIG = ../../config/pyproject.toml
GENERATED = .generated
DOCKER_COMPOSE = docker compose -f $(GENERATED)/docker-compose.yml --env-file $(GENERATED)/.env
UNIT_PYTEST = cd ../.. && PYTHONPATH=. PIPENV_PIPFILE=config/Pipfile pipenv run pytest systems/gcs/tests/unit

help:
	@echo "make prepare           - Собрать docker-compose + .env из компонентов"
	@echo "make docker-up         - Запустить систему (prepare + docker compose up)"
	@echo "make docker-up-no-broker - Запустить только сервисы GCS без брокера"
	@echo "make docker-down       - Остановить систему"
	@echo "make docker-down-no-broker - Остановить только сервисы GCS без брокера"
	@echo "make docker-logs       - Логи"
	@echo "make unit-test         - Unit-тесты GCS с coverage"
	@echo "make unit-test-cov     - Unit-тесты GCS с подробным coverage-отчётом"
	@echo "make integration-test  - Интеграционные тесты GCS (с поднятием стека)"
	@echo "make integration-test-no-up - Интеграционные тесты GCS без поднятия стека"
	@echo "make tests             - Все тесты GCS"
	@echo "make tests-no-up       - Unit + integration тесты без поднятия стека"

prepare:
	@cd ../.. && PIPENV_PIPFILE=config/Pipfile pipenv run python scripts/prepare_system.py systems/gcs

docker-up: prepare
	@set -a && . $(GENERATED)/.env && set +a && \
		$(DOCKER_COMPOSE) --profile $${BROKER_TYPE:-kafka} up -d --build

docker-up-no-broker: prepare
	@set -a && . $(GENERATED)/.env && set +a && \
		$(DOCKER_COMPOSE) --profile $${BROKER_TYPE:-kafka} up -d --build --no-deps \
		redis mission_store drone_store mission_converter orchestrator path_planner drone_manager

docker-down:
	-$(DOCKER_COMPOSE) --profile kafka down 2>/dev/null
	-$(DOCKER_COMPOSE) --profile mqtt down 2>/dev/null

docker-down-no-broker:
	-@set -a && . $(GENERATED)/.env && set +a && \
		$(DOCKER_COMPOSE) rm -sf mission_store drone_store mission_converter orchestrator path_planner drone_manager redis 2>/dev/null

docker-logs:
	@set -a && . $(GENERATED)/.env && set +a && \
		$(DOCKER_COMPOSE) --profile $${BROKER_TYPE:-kafka} logs -f

unit-test:
	@$(UNIT_PYTEST) --cov=systems.gcs --cov-config=systems/gcs/.coveragerc --cov-report=term

unit-test-cov:
	@$(UNIT_PYTEST) --cov=systems.gcs --cov-config=systems/gcs/.coveragerc --cov-report=term-missing --cov-report=xml:systems/gcs/.generated/unit-coverage.xml

integration-test: docker-up
	@echo "Waiting for broker and gcs components..."
	@sleep 30
	@set -a && . $(GENERATED)/.env && set +a && $(DOCKER_COMPOSE) --profile $${BROKER_TYPE:-kafka} ps
	@$(MAKE) integration-test-no-up

integration-test-no-up:
	@cd ../.. && set -a && . systems/gcs/$(GENERATED)/.env && set +a && \
		PYTHONPATH=. PIPENV_PIPFILE=config/Pipfile \
		pipenv run pytest systems/gcs/tests/integration

tests: unit-test integration-test

tests-no-up: unit-test integration-test-no-up
