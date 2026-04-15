.PHONY: help init unit-test tests ci-unit-test ci-integration-test ci-test docker-up docker-down docker-logs docker-ps docker-clean prepare-multi e2e-up e2e-test e2e-logs e2e-down e2e

PROJECT_ROOT := $(CURDIR)
DOCKER_COMPOSE = docker compose -f docker/docker-compose.yml --env-file docker/.env
LOAD_ENV = set -a && . docker/.env && set +a
PIPENV_PIPFILE = config/Pipfile
PYTEST_CONFIG = config/pyproject.toml

help:
	@echo "make init              - Установить pipenv и зависимости"
	@echo "make unit-test         - Unit тесты (SDK + broker + standalone компоненты)"
	@echo "make tests             - Все тесты"
	@echo "make ci-unit-test      - CI: unit тесты всех components/ и systems/"
	@echo "make ci-integration-test - CI: integration тесты всех systems/"
	@echo "make ci-test           - CI: unit + integration (все components/ и systems/)"
	@echo "make docker-up         - Запустить инфраструктуру брокера"
	@echo "make docker-down       - Остановить"
	@echo "make docker-logs       - Логи"
	@echo "make docker-ps         - Статус"
	@echo "make docker-clean      - Очистка"
	@echo "make prepare-multi SYSTEMS=\"drone_port gcs\" - Сгенерировать единый compose для нескольких систем"
	@echo "make e2e-up            - Поднять всё окружение E2E (4 системы + брокер + DroneAnalytics)"
	@echo "make e2e-test          - Запустить E2E тесты (pytest tests/e2e/)"
	@echo "make e2e-logs          - Показать события из DroneAnalytics"
	@echo "make e2e-down          - Остановить и очистить E2E окружение"
	@echo "make e2e               - e2e-up + e2e-test + e2e-logs + e2e-down"

init:
	@command -v pipenv >/dev/null 2>&1 || pip install pipenv
	PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv install --dev

unit-test:
	@PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run pytest -c $(PYTEST_CONFIG) \
		tests/unit/ \
		components/dummy_component/tests/ \
		-v

tests: unit-test

# --- CI: автообнаружение тестов во всех components/ и systems/ ---

ci-unit-test:
	@echo "=== SDK unit tests ==="
	@PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run pytest -c $(PYTEST_CONFIG) tests/unit/ -v
	@echo ""
	@fail=0; \
	for dir in components/*/ systems/*/; do \
		[ -d "$$dir" ] || continue; \
		if [ -d "$$dir/tests/unit" ]; then \
			echo "=== Unit tests: $$dir ==="; \
			PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run pytest -c $(PYTEST_CONFIG) "$$dir/tests/unit/" -v || fail=1; \
			echo ""; \
		elif [ -d "$$dir/tests" ] && ls "$$dir"/tests/test_*unit*.py >/dev/null 2>&1; then \
			echo "=== Unit tests (legacy): $$dir ==="; \
			PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run pytest -c $(PYTEST_CONFIG) "$$dir"/tests/test_*unit*.py -v || fail=1; \
			echo ""; \
		fi; \
	done; \
	if [ $$fail -ne 0 ]; then echo "=== Some unit tests FAILED ==="; exit 1; fi

ci-integration-test:
	@fail=0; \
	for dir in components/*/ systems/*/; do \
		[ -d "$$dir" ] || continue; \
		if [ -f "$$dir/Makefile" ] && grep -qE '^test-all-docker:|^integration-test:' "$$dir/Makefile" 2>/dev/null; then \
			target=$$(grep -oE '^(test-all-docker|integration-test):' "$$dir/Makefile" | head -1 | tr -d ':'); \
			echo "=== Integration tests: $$dir (make $$target) ==="; \
			$(MAKE) -C "$$dir" $$target PROJECT_ROOT=$(PROJECT_ROOT) || fail=1; \
			echo ""; \
		else \
			echo "=== Skipping $$dir (no integration target) ==="; \
		fi; \
	done; \
	if [ $$fail -ne 0 ]; then echo "=== Some integration tests FAILED ==="; exit 1; fi

ci-test: ci-unit-test ci-integration-test

docker-up:
	@test -f docker/.env || cp docker/example.env docker/.env
	@set -a && . docker/.env && set +a && \
		profiles="--profile $${BROKER_TYPE:-kafka}"; \
		[ "$${ENABLE_FABRIC:-false}" = "true" ] && profiles="$$profiles --profile fabric"; \
		$(DOCKER_COMPOSE) $$profiles up -d --build

docker-down:
	-$(DOCKER_COMPOSE) --profile kafka --profile fabric down 2>/dev/null
	-$(DOCKER_COMPOSE) --profile mqtt --profile fabric down 2>/dev/null

docker-logs:
	$(DOCKER_COMPOSE) --profile $$(grep BROKER_TYPE docker/.env | cut -d= -f2) logs -f

docker-ps:
	@docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

docker-clean:
	-$(DOCKER_COMPOSE) --profile kafka --profile fabric down -v --rmi local 2>/dev/null
	-$(DOCKER_COMPOSE) --profile mqtt --profile fabric down -v --rmi local 2>/dev/null

prepare-multi:
	@if [ -z "$(SYSTEMS)" ]; then \
		echo "Usage: make prepare-multi SYSTEMS=\"drone_port gcs\""; \
		exit 1; \
	fi
	@PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run python scripts/prepare_multi.py --systems $(SYSTEMS)

# ---------------------------------------------------------------------------
# E2E: full-scenario Docker test (4 systems + broker + DroneAnalytics)
# ---------------------------------------------------------------------------

E2E_SYSTEMS = Agregator insurer operator orvd_system regulator gcs
E2E_OUTPUT = .generated/e2e
E2E_COMPOSE = docker compose -f $(E2E_OUTPUT)/docker-compose.yml -f tests/e2e/analytics-compose.yml --env-file $(E2E_OUTPUT)/.env
E2E_PROFILE = kafka

e2e-up:
	@echo "=== Generating multi-system compose ==="
	@$(LOAD_ENV) && PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run python scripts/prepare_multi.py \
		--systems $(E2E_SYSTEMS) --output $(E2E_OUTPUT)
	@echo "ANALYTICS_URL=http://analytics-backend:8080" >> $(E2E_OUTPUT)/.env
	@echo "ANALYTICS_API_KEY=test-api-key-e2e-12345" >> $(E2E_OUTPUT)/.env
	@echo "ANALYTICS_PORT=8090" >> $(E2E_OUTPUT)/.env
	@echo "DELIVERY_DRONE_HEALTH_PORT=8095" >> $(E2E_OUTPUT)/.env
	@echo "=== Starting E2E environment ==="
	$(E2E_COMPOSE) --profile $(E2E_PROFILE) up -d --build
	@echo "=== Waiting for services to start ==="
	@for i in $$(seq 1 30); do \
		curl -sf http://localhost:8080/health >/dev/null 2>&1 && break; \
		sleep 3; \
	done
	@echo "=== E2E environment is up ==="

e2e-test:
	@echo "=== Running E2E tests ==="
	@$(LOAD_ENV) && PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run pytest tests/e2e/test_e2e_scenario.py -v -s \
		--tb=short 2>&1 || (echo "E2E tests failed"; exit 1)

e2e-logs:
	@echo "=== Fetching events from DroneAnalytics ==="
	@TOKEN=$$(curl -sf -X POST http://localhost:8090/auth/login \
		-H 'Content-Type: application/json' \
		-d '{"username":"admin","password":"admin1234"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null) && \
	curl -sf http://localhost:8090/log/event?limit=100 \
		-H "Authorization: Bearer $$TOKEN" | python3 -m json.tool 2>/dev/null || \
	echo "(DroneAnalytics not available or no events)"

e2e-down:
	@echo "=== Stopping E2E environment ==="
	-$(E2E_COMPOSE) --profile $(E2E_PROFILE) down -v 2>/dev/null
	@echo "=== E2E environment stopped ==="

e2e: e2e-up e2e-test e2e-logs e2e-down
