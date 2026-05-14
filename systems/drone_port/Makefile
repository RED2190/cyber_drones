.PHONY: help prepare unit-test unit-test-cov integration-test integration-test-no-up tests tests-no-up docker-up docker-up-no-broker docker-down docker-down-no-broker docker-logs docker-clean

PIPENV_PIPFILE = ../../config/Pipfile
PYTEST_CONFIG = ../../config/pyproject.toml
GENERATED = .generated
DOCKER_COMPOSE = docker compose -f $(GENERATED)/docker-compose.yml --env-file $(GENERATED)/.env
UNIT_PYTEST = cd ../.. && PYTHONPATH=. PIPENV_PIPFILE=config/Pipfile pipenv run pytest systems/drone_port/tests/unit

help:
	@echo "make prepare           - Собрать docker-compose + .env из компонентов"
	@echo "make docker-up         - Запустить систему (prepare + docker compose up)"
	@echo "make docker-up-no-broker - Запустить только сервисы DronePort без брокера"
	@echo "make docker-down       - Остановить систему"
	@echo "make docker-down-no-broker - Остановить только сервисы DronePort без брокера"
	@echo "make docker-logs       - Логи"
	@echo "make docker-clean      - Очистка docker ресурсов системы"
	@echo "make unit-test         - Unit-тесты DronePort с coverage"
	@echo "make unit-test-cov     - Unit-тесты DronePort с подробным coverage-отчётом"
	@echo "make integration-test  - Интеграционные тесты DronePort с поднятием стека"
	@echo "make integration-test-no-up - Интеграционные тесты DronePort без поднятия стека"
	@echo "make tests             - Все тесты DronePort"
	@echo "make tests-no-up       - Unit + integration тесты без поднятия стека"

prepare:
	@cd ../.. && PIPENV_PIPFILE=config/Pipfile pipenv run python scripts/prepare_system.py systems/drone_port

docker-up: prepare
	@set -a && . $(GENERATED)/.env && set +a && \
		$(DOCKER_COMPOSE) --profile $${BROKER_TYPE:-mqtt} up -d --build

docker-up-no-broker: prepare
	@set -a && . $(GENERATED)/.env && set +a && \
		$(DOCKER_COMPOSE) --profile $${BROKER_TYPE:-mqtt} up -d --build --no-deps \
		redis state_store port_manager drone_registry charging_manager drone_manager orchestrator gateway

docker-down:
	-$(DOCKER_COMPOSE) --profile kafka down 2>/dev/null
	-$(DOCKER_COMPOSE) --profile mqtt down 2>/dev/null

docker-down-no-broker:
	-@set -a && . $(GENERATED)/.env && set +a && \
		$(DOCKER_COMPOSE) rm -sf state_store port_manager drone_registry charging_manager drone_manager orchestrator gateway redis 2>/dev/null

docker-logs:
	@set -a && . $(GENERATED)/.env && set +a && \
		$(DOCKER_COMPOSE) --profile $${BROKER_TYPE:-mqtt} logs -f

docker-clean:
	-$(DOCKER_COMPOSE) --profile kafka down -v --rmi local 2>/dev/null
	-$(DOCKER_COMPOSE) --profile mqtt down -v --rmi local 2>/dev/null

unit-test:
	@$(UNIT_PYTEST) --cov=systems.drone_port --cov-config=systems/drone_port/.coveragerc --cov-report=term

unit-test-cov:
	@$(UNIT_PYTEST) --cov=systems.drone_port --cov-config=systems/drone_port/.coveragerc --cov-report=term-missing --cov-report=xml:systems/drone_port/.generated/unit-coverage.xml

integration-test: docker-up
	@echo "Waiting for broker and drone_port components..."
	@sleep 30
	@set -a && . $(GENERATED)/.env && set +a && $(DOCKER_COMPOSE) --profile $${BROKER_TYPE:-mqtt} ps
	@$(MAKE) integration-test-no-up
	-$(MAKE) docker-down

integration-test-no-up:
	@cd ../.. && set -a && . systems/drone_port/$(GENERATED)/.env && set +a && \
		PYTHONPATH=. PIPENV_PIPFILE=config/Pipfile \
		pipenv run pytest systems/drone_port/tests/integration

tests: unit-test integration-test

tests-no-up: unit-test integration-test-no-up
