.PHONY: help sitl-net sitl-env sitl-up sitl-down sitl-ps sitl-logs

# Запускать из корня SITL-module (где docker-compose.yaml).

SITL_ENV ?= sitl.env
COMPOSE = docker compose -f docker-compose.yaml --env-file $(SITL_ENV)

# Путь к cyber_drons/docker/.env — те же ADMIN_USER / ADMIN_PASSWORD / DOCKER_NETWORK, что у Mosquitto.
# Если файла нет, берётся sitl.env.example → sitl.env
BROKER_ENV_FILE ?= $(abspath $(CURDIR)/../../../cyber_drons/docker/.env)

help:
	@echo ""
	@echo "  make sitl-net    Создать сеть drones_net (если ещё нет)"
	@echo "  make sitl-env    Собрать sitl.env из BROKER_ENV_FILE или из sitl.env.example"
	@echo "  make sitl-up     sitl-net + sitl-env + docker compose up"
	@echo "  make sitl-down   Остановить контейнеры"
	@echo "  make sitl-ps     Статус"
	@echo "  make sitl-logs   Логи (follow)"
	@echo ""

sitl-net:
	@docker network create drones_net 2>/dev/null || true

sitl-env:
	@if [ -f "$(BROKER_ENV_FILE)" ]; then \
		echo "sitl.env ← $(BROKER_ENV_FILE)"; \
		python3 "$(CURDIR)/generate_sitl_env.py" "$(BROKER_ENV_FILE)" -o "$(SITL_ENV)"; \
	else \
		echo "Файл $(BROKER_ENV_FILE) не найден — копирую sitl.env.example → $(SITL_ENV)"; \
		test -f "$(SITL_ENV)" || cp sitl.env.example "$(SITL_ENV)"; \
	fi

sitl-up: sitl-net sitl-env
	@$(COMPOSE) up -d --build
	@echo ""
	@echo "Готово: make sitl-ps  /  make sitl-logs"

sitl-down:
	@$(COMPOSE) down

sitl-ps:
	@$(COMPOSE) ps

sitl-logs:
	@$(COMPOSE) logs -f --tail=100
