.PHONY: help init unit-test integration-test integration-test-run tests docker-up docker-down docker-logs docker-ps docker-clean gcs-system-up gcs-system-down drone-port-system-up drone-port-system-down web-demo

DOCKER_COMPOSE = docker compose -f docker/docker-compose.yml --env-file docker/.env
LOAD_ENV = set -a && . docker/.env && set +a
PIPENV_PIPFILE = config/Pipfile
PYTEST_CONFIG = config/pyproject.toml
GCS_COMPOSE = docker compose -f systems/gcs/.generated/docker-compose.yml --env-file systems/gcs/.generated/.env
DRONE_PORT_COMPOSE = docker compose -f systems/drone_port/.generated/docker-compose.yml --env-file systems/drone_port/.generated/.env
PYTEST_COV_OPTS = --cov=. --cov-report=term-missing --cov-report=xml:coverage.xml --cov-report=html:htmlcov
ARTIFACTS_DIR = artifacts
PYTEST_JUNIT_OPTS = --junitxml=$(ARTIFACTS_DIR)/pytest-unit.xml

help:
	@echo "make init              - Установить pipenv и зависимости"
	@echo "make unit-test         - Unit тесты (SDK + broker + standalone компоненты)"
	@echo "make integration-test  - Интеграционные тесты (общие + gcs + drone_port, docker required)"
	@echo "make integration-test-run - Только запуск integration pytest без lifecycle docker"
	@echo "make tests             - Все тесты"
	@echo "make docker-up         - Запустить инфраструктуру брокера"
	@echo "make docker-down       - Остановить"
	@echo "make docker-logs       - Логи"
	@echo "make docker-ps         - Статус"
	@echo "make docker-clean      - Очистка"
	@echo "make gcs-system-up     - Поднять GCS"
	@echo "make gcs-system-down   - Остановить GCS"
	@echo "make drone-port-system-up   - Поднять DronePort"
	@echo "make drone-port-system-down - Остановить DronePort"
	@echo "make web-demo         - Запустить веб-сервер demo через pipenv"

init:
	@git submodule update --init --recursive
	@command -v pipenv >/dev/null 2>&1 || pip install pipenv
	PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv install --dev

unit-test:
	@mkdir -p $(ARTIFACTS_DIR)
	@PIPENV_PIPFILE=$(PIPENV_PIPFILE) PYTHONPATH=. pipenv run pytest -c $(PYTEST_CONFIG) $(PYTEST_JUNIT_OPTS) \
		tests/unit/ \
		components/dummy_component/tests/ \
		systems/gcs/tests/unit/ \
		systems/drone_port/tests/unit/ \
		-v

integration-test: docker-up gcs-system-up drone-port-system-up
	@$(MAKE) integration-test-run
	-$(MAKE) drone-port-system-down
	-$(MAKE) gcs-system-down
	-$(MAKE) docker-down

integration-test-run:
	@$(LOAD_ENV) && PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run pytest -c $(PYTEST_CONFIG) \
		tests/integration/ \
		systems/gcs/tests/integration/test_gcs_integration.py \
		systems/drone_port/tests/integration/test_drone_port_integration.py \
		-v

gcs-system-up: 
	@$(MAKE) -C systems/gcs prepare
	@set -a && . systems/gcs/.generated/.env && set +a && \
		$(GCS_COMPOSE) --profile $${BROKER_TYPE:-kafka} up -d --build --no-deps \
		redis mission_store drone_store mission_converter orchestrator path_planner drone_manager

gcs-system-down:
	-@set -a && . systems/gcs/.generated/.env && set +a && \
		$(GCS_COMPOSE) rm -sf redis mission_store drone_store mission_converter orchestrator path_planner drone_manager 2>/dev/null

drone-port-system-up:
	@$(MAKE) -C systems/drone_port prepare
	@set -a && . systems/drone_port/.generated/.env && set +a && \
		$(DRONE_PORT_COMPOSE) --profile $${BROKER_TYPE:-mqtt} up -d --build --no-deps \
		redis state_store port_manager drone_registry charging_manager drone_manager orchestrator

drone-port-system-down:
	-@set -a && . systems/drone_port/.generated/.env && set +a && \
		$(DRONE_PORT_COMPOSE) rm -sf redis state_store port_manager drone_registry charging_manager drone_manager orchestrator 2>/dev/null

web-demo:
	@PYTHONPATH=. PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run python demo/web_demo.py

tests: unit-test integration-test

docker-up:
	@test -f docker/.env || cp docker/example.env docker/.env
	@$(LOAD_ENV) && profile="--profile $${BROKER_TYPE:-kafka}"; \
	$(DOCKER_COMPOSE) $$profile up -d

docker-down:
	-$(DOCKER_COMPOSE) --profile kafka down 2>/dev/null
	-$(DOCKER_COMPOSE) --profile mqtt down 2>/dev/null

docker-logs:
	$(DOCKER_COMPOSE) --profile $$(grep BROKER_TYPE docker/.env | cut -d= -f2) logs -f
	
docker-ps:
	@docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

docker-clean:
	-$(DOCKER_COMPOSE) --profile kafka down -v --rmi local 2>/dev/null
	-$(DOCKER_COMPOSE) --profile mqtt down -v --rmi local 2>/dev/null
