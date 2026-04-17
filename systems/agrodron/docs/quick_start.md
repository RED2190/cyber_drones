# Quick Start

Брокер (Kafka/MQTT), SDK и система **AgroDron** в каталоге `systems/agrodron/`. Сборка Docker для системы выполняется через `scripts/prepare_system.py` (см. `make prepare` в `systems/agrodron/`).

## Структура

```
systems/agrodron/            Система AgroDron: docker-compose компонентов, Makefile, tests/
  components/        Компоненты (autopilot, mission_handler, security_monitor, …)
  tests/integration/ Интеграционные тесты (in-process)
broker/              SystemBus, MQTTSystemBus, KafkaSystemBus
sdk/                 BaseComponent, topic_utils
docker/              Инфраструктура брокера (Kafka, Mosquitto), example.env
scripts/             prepare_system.py — слияние compose и .env
config/              Pipfile, pyproject.toml (pytest)
docs/                SYSTEM.md, EXTERNAL_API.md, quick_start.md
```

## Окружение и тесты (из корня репозитория)

Зависимости задаются в `config/Pipfile`:

```bash
PIPENV_PIPFILE=config/Pipfile pipenv install
cd systems/agrodron && make unit-test          # только unit
cd systems/agrodron && make test               # unit + integration
```

Только брокер (без контейнеров AgroDron): скопируйте `docker/example.env` в `docker/.env`, затем поднимите compose из `docker/` (см. [docker/README.md](../docker/README.md)).

## Команды Makefile

Корневого `Makefile` нет: все цели `make` описаны в `systems/agrodron/Makefile`.

## AgroDron

```bash
cd systems/agrodron
make prepare       # Собрать .generated/
make test          # Unit + integration тесты
make docker-up     # Брокер + все компоненты
make docker-ps     # Статус контейнеров
make docker-logs   # Логи
make docker-down   # Остановить
```

## Протокол сообщений

Все сообщения — JSON с полями: `action`, `payload`, `sender`, `correlation_id`, `reply_to`.

- **Топики**: `v1.{SystemName}.{InstanceID}.{component}` (например `v1.Agrodron.Agrodron001.autopilot`)
- **sender**: полный топик отправителя (не короткое имя)
- **action**: всегда lowercase (`get_state`, `set_target`, `log_event`)

## Правило доступа компонентов

Все компоненты (кроме МБ) принимают запросы **только от монитора безопасности**. Сообщения от любого другого sender игнорируются. МБ проксирует запросы от своего топика, поэтому целевой компонент видит `sender = v1.Agrodron.Agrodron001.security_monitor`.

Поток:

1. Клиент отправляет `proxy_request` / `proxy_publish` на топик security_monitor
2. МБ проверяет политику `(sender, topic, action)`
3. МБ проксирует сообщение к целевому компоненту от своего sender
4. Целевой компонент проверяет sender и обрабатывает запрос

## Docker (полная система AgroDron)

```bash
cp docker/example.env docker/.env   # при необходимости скорректируйте BROKER_TYPE и пароли
cd systems/agrodron
make prepare          # systems/agrodron/.generated/docker-compose.yml и .env
make docker-up        # брокер + все компоненты (профиль из BROKER_TYPE в смерженном .env)
make docker-down
```

Переменные `BROKER_TYPE`, `ADMIN_USER`, `ADMIN_PASSWORD` задаются в `docker/.env` и `systems/agrodron/.env` (итог — в `systems/agrodron/.generated/.env`). Топики: `TOPIC_VERSION`, `SYSTEM_NAME`, `INSTANCE_ID`.

При **MQTT** при нагрузке на монитор безопасности имеет значение размер пула обработки входящих сообщений — **`MQTT_BUS_CALLBACK_WORKERS`** (по умолчанию 32, см. [SYSTEM.md](SYSTEM.md) → раздел про MQTT и этот параметр).

## Документация

- [docs/SYSTEM.md](SYSTEM.md) — полная документация системы AgroDron
- [docs/EXTERNAL_API.md](EXTERNAL_API.md) — API для внешних систем (НУС, ОРВД, Дронопорт, SITL)
