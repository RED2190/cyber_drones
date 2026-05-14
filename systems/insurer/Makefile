.PHONY: help unit-test integration-test tests docker-up docker-down docker-logs wait-kafka

CORE_SERVICES = zookeeper kafka kafdrop insurance-service
TEST_SERVICE = tests
INSURANCE_REPLICAS ?= 1
INSURANCE_INSTANCE_ID ?=
TEST_INSTANCE_ID ?= 1
COMPOSE_FILE ?= docker-compose.yml
TEST_COMPOSE_FILE ?= docker-compose.dev.yml
DOCKER_COMPOSE = docker compose -f $(COMPOSE_FILE)

help:
	@echo "make docker-up         - Запустить систему (по умолчанию 1 реплика insurance-service)"
	@echo "                         Пример: make docker-up INSURANCE_REPLICAS=3"
	@echo "                         Опционально: make docker-up INSURANCE_INSTANCE_ID=1"
	@echo "make docker-down       - Остановить систему"
	@echo "make docker-logs       - Логи"
	@echo "make unit-test         - Unit тесты компонентов"
	@echo "make integration-test  - Интеграционные тесты (docker required)"
	@echo "make wait-kafka        - Дождаться готовности Kafka"
	@echo "make tests             - Все тесты"

docker-up:
	@INSURANCE_INSTANCE_ID=$(INSURANCE_INSTANCE_ID) $(DOCKER_COMPOSE) up -d --build --scale insurance-service=$(INSURANCE_REPLICAS) $(CORE_SERVICES)

docker-down:
	@$(DOCKER_COMPOSE) down 2>/dev/null

docker-logs:
	@$(DOCKER_COMPOSE) logs -f

unit-test:
	@mvn test

wait-kafka:
	@for i in $$(seq 1 120); do \
		$(DOCKER_COMPOSE) exec -T kafka sh -lc '/opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:29092 --list >/dev/null 2>&1' && \
		echo "Kafka is ready" && exit 0; \
		echo "Waiting for Kafka metadata... ($$i/120)"; \
		sleep 2; \
	done; \
	echo "Kafka is not ready in time"; \
	exit 1

integration-test:
	@$(MAKE) docker-up COMPOSE_FILE=$(TEST_COMPOSE_FILE) INSURANCE_REPLICAS=1 INSURANCE_INSTANCE_ID=$(TEST_INSTANCE_ID)
	@$(MAKE) wait-kafka COMPOSE_FILE=$(TEST_COMPOSE_FILE)
	@INSURER_INSTANCE_ID=$(TEST_INSTANCE_ID) docker compose -f $(TEST_COMPOSE_FILE) run --build --rm --entrypoint go $(TEST_SERVICE) test -race -v ./...
	-$(MAKE) docker-down COMPOSE_FILE=$(TEST_COMPOSE_FILE)

tests: unit-test integration-test