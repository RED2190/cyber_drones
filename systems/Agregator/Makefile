.PHONY: help build test unit-test integration-test docker-up docker-up-dev docker-down docker-logs

help:
	@echo "make build       - build gateway binary"
	@echo "make tests       - run all tests"
	@echo "make unit-test   - run unit tests"
	@echo "make integration-test - run integration tests in docker compose"
	@echo "make docker-up   - start postgres + aggregator via docker compose kafka profile"
	@echo "make docker-up-dev - start local dev stack with kafka"
	@echo "make docker-down - stop docker compose services"
	@echo "make docker-logs - follow service logs"

build:
	go build -o bin/agregator ./src/gateway

tests: unit-test integration-test

unit-test:
	go test ./...

integration-test:
	@docker network create $${DOCKER_NETWORK:-drones_net} >/dev/null 2>&1 || true
	@docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile kafka --profile tests up -d --build aggregator postgres zookeeper kafka kafka-init
	@docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile kafka --profile tests run --build --rm tests
	@docker compose -f docker-compose.yml -f docker-compose.dev.yml down -v --remove-orphans

docker-up:
	docker compose --profile kafka up -d --build

docker-up-dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile kafka up -d --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f
