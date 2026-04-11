# Quick Start

Брокер (Kafka/MQTT) + SDK. Шаблоны: `components/dummy_component`, `systems/dummy_system`.

## Структура

```
broker/              Шина, create_system_bus
sdk/                 BaseComponent, BaseSystem
components/          Standalone-компоненты
systems/             Системы (dummy_system)
docker/              Брокер (kafka, mosquitto)
scripts/             prepare_system.py
config/              Pipfile, pyproject.toml
```

## Команды

```bash
make init          # pipenv + зависимости
make unit-test     # Unit тесты
make docker-up     # Брокер (kafka/mqtt)
make docker-down
```

**Система:**
```bash
cd systems/dummy_system
make prepare       # Собрать .generated/
make docker-up    # Брокер + компоненты
make unit-test
make test-all-docker
```

## Протокол

Сообщения — dict: `action`, `payload`, `sender`, `correlation_id`, `reply_to`.

## Топики

| Шаблон | Назначение | Пример |
|--------|------------|--------|
| `systems.<имя_системы>` | Входной топик системы (Gateway) | `systems.flight_system` |
| `components.<имя_компонента>` | Топик компонента | `components.gps_sensor` |
| `errors.dead_letters` | Ошибки fire-and-forget | — |

### SYSTEM_NAMESPACE — изоляция экземпляров

Если на одном брокере работают несколько экземпляров одной системы
(например, два `flight_system` с одинаковыми компонентами), топики совпадут.

Чтобы этого избежать, задайте переменную окружения `SYSTEM_NAMESPACE`.
Она автоматически добавляет префикс ко всем топикам:

| `SYSTEM_NAMESPACE` | Итоговый топик системы | Итоговый топик компонента |
|--------------------|------------------------|---------------------------|
| *(не задан)* | `systems.flight_system` | `components.gps_sensor` |
| `fleet_1` | `fleet_1.systems.flight_system` | `fleet_1.components.gps_sensor` |
| `fleet_2` | `fleet_2.systems.flight_system` | `fleet_2.components.gps_sensor` |

В `docker-compose.yml` или `.env` системы:

```yaml
environment:
  - SYSTEM_NAMESPACE=fleet_1
```

Если `SYSTEM_NAMESPACE` не задан — топики без префикса, всё работает как раньше.

### Межсистемное взаимодействие

Внешняя система отправляет запрос на топик `systems.<имя_системы>`,
не зная внутренних компонентов. Gateway (`BaseGateway`) по таблице
`ACTION_ROUTING` маршрутизирует запрос к нужному компоненту
и возвращает ответ отправителю.

> **Dead Letter Topic.**
> Если сообщение пришло без `reply_to` (fire-and-forget) и обработка
> завершилась ошибкой или action не найден, оно отправляется
> в `errors.dead_letters`. При наличии `reply_to` ошибка возвращается
> отправителю как обычный ответ.

## Свой компонент/система

- **Компонент:** `components/README.MD`
- **Система:** `systems/README.md`

## Docker

```bash
cp docker/example.env docker/.env
# BROKER_TYPE=kafka или mqtt
make docker-up
```

| Переменная | Описание |
|------------|----------|
| BROKER_TYPE | kafka / mqtt |
| ADMIN_USER, ADMIN_PASSWORD | Админ брокера |
| COMPONENT_USER_A/B | Опционально, для компонентов |

## Troubleshooting

- Брокер недоступен: проверьте profile (kafka/mqtt) в docker-up
- Внутри Docker: имена контейнеров (kafka, mosquitto), не localhost
