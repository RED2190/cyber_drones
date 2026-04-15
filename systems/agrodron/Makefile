.PHONY: help prepare unit-test integration-test test docker-up docker-up-components docker-down docker-logs docker-logs-% docker-ps status monitor-help

# Все команды pipenv/pytest выполняются из каталога systems/agrodron.
PIPENV       = PIPENV_PIPFILE=config/Pipfile pipenv
REPO_ROOT    = $(abspath ../..)
PYTEST       = PYTHONPATH=$(REPO_ROOT):$$PYTHONPATH $(PIPENV) run pytest -c config/pyproject.toml
GENERATED    = .generated
COMPOSE      = docker compose -f $(GENERATED)/docker-compose.yml --env-file $(GENERATED)/.env
BROKER       = $${BROKER_TYPE:-mqtt}

# Только сервисы AgroDron (без kafka/mosquitto). Брокер должен быть уже запущен и доступен по MQTT_BROKER.
COMPONENT_SERVICES = gateway security_monitor journal navigation autopilot limiter emergensy mission_handler motors sprayer telemetry system_monitor

help:
	@echo ""
	@echo "  Подготовка"
	@echo "    make prepare             Собрать $(GENERATED)/docker-compose.yml + .env"
	@echo ""
	@echo "  Тесты (без Docker)"
	@echo "    make unit-test           Unit-тесты компонентов (src/*/tests/)"
	@echo "    make integration-test    Интеграционные тесты in-process (tests/integration/)"
	@echo "    make test                Все тесты (unit + integration)"
	@echo ""
	@echo "  Docker"
	@echo "    make docker-up           Поднять систему (prepare + брокер + компоненты)"
	@echo "    make docker-up-components Только контейнеры компонентов (брокер уже снаружи; см. MQTT_BROKER)"
	@echo "    make docker-down         Остановить и удалить контейнеры"
	@echo "    make docker-ps           Статус контейнеров"
	@echo "    make docker-logs         Логи всех контейнеров (follow)"
	@echo "    make docker-logs-<svc>   Логи конкретного сервиса, например:"
	@echo "                               make docker-logs-security_monitor"
	@echo "                               make docker-logs-autopilot"
	@echo "                               make docker-logs-system_monitor"
	@echo ""
	@echo "  Монитор системы (журнал + телеметрия, веб-UI)"
	@echo "    make monitor-help        Как открыть панель в браузере и смотреть логи"
	@echo ""
	@echo "  Полный цикл"
	@echo "    make status              prepare + test + docker-up + docker-ps"
	@echo ""

# ---------------------------------------------------------------------------
#  Подготовка
# ---------------------------------------------------------------------------

prepare:
	@$(PIPENV) install --dev
	@$(PIPENV) run python scripts/prepare_system.py .

# ---------------------------------------------------------------------------
#  Тесты
# ---------------------------------------------------------------------------

unit-test:
	@echo "=== Unit-тесты компонентов ==="
	@$(PYTEST) src/*/tests/ -v --tb=short

integration-test:
	@echo "=== Интеграционные тесты (in-process) ==="
	@$(PYTEST) tests/integration/ -v --tb=short

test: unit-test integration-test
	@echo ""
	@echo "Все тесты пройдены."

# ---------------------------------------------------------------------------
#  Docker
# ---------------------------------------------------------------------------

docker-up: prepare
	@set -a && . $(GENERATED)/.env && set +a && \
		$(COMPOSE) --profile $(BROKER) up -d --build
	@echo ""
	@echo "Система запущена. Проверьте статус: make docker-ps"
	@echo "Логи:                          make docker-logs"
	@echo "Монитор (журнал/телеметрия):   make monitor-help"

docker-up-components: prepare
	@echo "Запуск только компонентов AgroDron (без kafka/mosquitto). Брокер должен быть в той же Docker-сети; MQTT_BROKER по умолчанию — hostname mosquitto."
	@set -a && . $(GENERATED)/.env && set +a && \
		$(COMPOSE) --profile $(BROKER) up -d --build --no-deps $(COMPONENT_SERVICES)
	@echo ""
	@echo "Компоненты запущены. Статус: make docker-ps"
	@echo "Монитор (журнал/телеметрия):   make monitor-help"

monitor-help:
	@echo ""
	@echo "  System monitor — веб-панель над журналом и снимком телеметрии"
	@echo "  После make docker-up или make docker-up-components контейнер system_monitor поднимается вместе с остальными."
	@echo ""
	@echo "  Открыть в браузере (по умолчанию порт 8090 на хосте):"
	@echo "    http://localhost:8090/"
	@echo "  Если задали другой порт: export SYSTEM_MONITOR_HOST_PORT=9090 перед make prepare && make docker-up"
	@echo "  Проверка API: curl -s http://localhost:8090/api/snapshot | head"
	@echo ""
	@echo "  Логи сервиса:"
	@echo "    make docker-logs-system_monitor"
	@echo ""

docker-down:
	-@$(COMPOSE) --profile mqtt  down --remove-orphans 2>/dev/null
	-@$(COMPOSE) --profile kafka down --remove-orphans 2>/dev/null

docker-ps:
	@set -a && . $(GENERATED)/.env 2>/dev/null && set +a && \
		$(COMPOSE) --profile $(BROKER) ps

docker-logs:
	@set -a && . $(GENERATED)/.env && set +a && \
		$(COMPOSE) --profile $(BROKER) logs -f --tail=100

docker-logs-%:
	@set -a && . $(GENERATED)/.env && set +a && \
		$(COMPOSE) --profile $(BROKER) logs -f --tail=100 $*

# ---------------------------------------------------------------------------
#  Полный цикл
# ---------------------------------------------------------------------------

status: prepare test
	@echo ""
	@echo "=== Запуск Docker ==="
	@$(MAKE) docker-up
	@sleep 5
	@$(MAKE) docker-ps
