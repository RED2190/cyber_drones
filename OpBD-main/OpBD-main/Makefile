.PHONY: help init unit-test tests ci-unit-test ci-integration-test ci-test docker-up docker-down docker-logs docker-ps docker-clean

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
	@if [ -d components ] && ls -d components/*/ >/dev/null 2>&1; then \
		for comp in components/*/; do \
			if [ -d "$$comp/tests" ]; then \
				echo "=== Unit tests: $$comp ==="; \
				PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run pytest -c $(PYTEST_CONFIG) "$$comp/tests/" -v || exit 1; \
				echo ""; \
			fi; \
		done; \
	fi
	@for sys in systems/*/; do \
		if ls "$$sys"/tests/test_*unit*.py >/dev/null 2>&1; then \
			echo "=== Unit tests: $$sys ==="; \
			PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run pytest -c $(PYTEST_CONFIG) "$$sys"/tests/test_*unit*.py -v || exit 1; \
			echo ""; \
		fi; \
	done

ci-integration-test:
	@for sys in systems/*/; do \
		if [ -f "$$sys/Makefile" ] && grep -q 'test-all-docker' "$$sys/Makefile" 2>/dev/null; then \
			echo "=== Integration tests: $$sys ==="; \
			$(MAKE) -C "$$sys" test-all-docker || exit 1; \
			echo ""; \
		elif ls "$$sys"/tests/test_integration*.py >/dev/null 2>&1; then \
			echo "=== Integration tests (pytest): $$sys ==="; \
			PIPENV_PIPFILE=$(PIPENV_PIPFILE) pipenv run pytest -c $(PYTEST_CONFIG) "$$sys"/tests/test_integration*.py -v || exit 1; \
			echo ""; \
		fi; \
	done

ci-test: ci-unit-test ci-integration-test

docker-up:
	@test -f docker/.env || cp docker/example.env docker/.env
	@profile=$${BROKER_TYPE:-$$(grep '^BROKER_TYPE=' docker/.env 2>/dev/null | cut -d= -f2)}; \
	profile=$${profile:-kafka}; \
	$(DOCKER_COMPOSE) --profile $$profile up -d

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
