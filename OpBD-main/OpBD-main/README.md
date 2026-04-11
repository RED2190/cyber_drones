# OpBD
Система организации воздушного движения беспилотных автономных систем


## Требования

- **Python 3.11+**
- **pipenv** (установка: `pip install pipenv`)
- **Docker** и **Docker Compose** (для запуска системы в контейнерах и для интеграционных тестов)
- На **Windows**: для команд `make` нужен WSL или Git Bash (либо выполняйте команды вручную)

Зависимости проекта задаются в `config/Pipfile`. Из корня репозитория:

```bash
cd config
pipenv install
pipenv install --dev
cd ..
```

---

## 1. Поднять систему OrvdSystem (Docker)

Система состоит из компонента OrvdComponent и OrvdGateway. Все топики для взаимодействия компонентов находятся в `systems/orvd_system/src/gateway/topics.py.`

### 1.1. Настройка брокера

В `docker/.env` задайте брокер:

- **Kafka**: `BROKER_TYPE=kafka`
- **MQTT**: `BROKER_TYPE=mqtt`

Если не задано, по умолчанию используется `kafka`.

### 1.2. Поднятие системы

```bash
cd orvd_system
make docker-up
```

Эта команда:

1. Собирает `.generated/.env` и `docker-compose.yml` для системы.
2. Поднимает брокер (Kafka или Mosquitto) и все сервисы системы с профилем `kafka` или `mqtt`.

Эквивалент вручную (без make):

```bash
cd orvd_system
# подставить kafka или mqtt
docker compose -f .generated/docker-compose.yml --env-file .generated/.env --profile mqtt up -d --build
```

### 1.3. Проверка, что всё запущено

```bash
docker ps
```

Должны быть контейнеры: брокер (kafka или mosquitto), orvd_gateway, orvd_component.

### 1.4. Логи

**Все контейнеры:**

```bash
cd orvd_system
make docker-logs
```

**Логи конкретного контейнера:**

```bash
# Только gateway
docker compose -f .generated/docker-compose.yml --env-file .generated/.env logs --tail=100 orvd_gateway

# Только component
docker compose -f .generated/docker-compose.yml --env-file .generated/.env logs --tail=100 orvd_component
```

---

## 2. Топики и формат сообщений

| Топик                    | Формат / Пример сообщения                                                                                                                                |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `drone/mission/request`  | `{ "drone_id": "string", "mission_id": "number", "time": "timestamp", "coords": { "lat": 0.0, "lon": 0.0 }, "velocity": 10.0, "drone_status": "ready" }` |
| `drone/mission/response` | `{ "status": "mission_registered", "mission_id": "123", "from": "orvd_component" }`                                                                      |
| `drone/takeoff/request`  | `{ "drone_id": "string", "mission_id": "number", "time": "timestamp", "coords": { "lat": 0.0, "lon": 0.0 } }`                                            |
| `ordv/authorization`     | `{ "authorized": "true/false" }`                                                                                                                         |
| `drone/telemetry`        | `{ "drone_id": "string", "coords": { "lat": 0.0, "lon": 0.0 } }`                                                                                         |
| `ordv/no_fly_zones`      | `{ "zone_id": "string", "type": "fly/no_fly", "coords": [[lat, lon],...], "active": "true/false" }`                                                      |
| `ordv/emergency`         | `{ "command": "string", "drone_id": "string", "time": "timestamp" }`                                                                                     |

### 2.1 Подробнее

- Регистрация дрона (эксплуатант -> ОРВД)

Action: `register_drone`

Payload:
```JSON
{
  "drone_id": "DRONE123",
  "model": "DJI Phantom",
  "operator": "Operator1",
  "additional_info": {}
}
```
Response:
```JSON
{
  "status": "registered",
  "drone_id": "DRONE123",
  "from": "orvd_component"
}
```

- Регистрация миссии (эксплуатант -> ОРВД)

Action: `register_mission`

Payload:
```JSON
{
  "mission_id": 101,
  "drone_id": "DRONE123",
  "route": [
    {"lat": 55.7558, "lon": 37.6173},
    {"lat": 55.7560, "lon": 37.6180}
  ],
  "time": "2026-03-17T12:00:00Z",
  "velocity": 10.5
}
```
Response:

Если маршрут разрешён:
```JSON
{
  "status": "mission_registered",
  "mission_id": 101,
  "from": "orvd_component"
}
```
Если маршрут пересекает запретную зону:
```JSON
{
  "status": "rejected",
  "reason": "route intersects no_fly_zone",
  "from": "orvd_component"
}
```

- Авторизация миссии (ОРВД)

Action: `authorize_mission`

Payload:
```JSON
{
  "mission_id": 101
}
```
Response:
```JSON
{
  "status": "authorized",
  "mission_id": 101,
  "from": "orvd_component"
}
```

- Запрос взлета (дрон -> ОРВД)

Action: `request_takeoff`

Payload:
```JSON
{
  "drone_id": "DRONE123",
  "mission_id": 101,
  "time": "2026-03-17T12:05:00Z"
}
```
Response:

Если разрешено:
```JSON
{
  "status": "takeoff_authorized",
  "drone_id": "DRONE123",
  "mission_id": 101,
  "from": "orvd_component"
}
```
Если миссия не авторизована:
```JSON
{
  "status": "denied",
  "reason": "mission not authorized"
}
```

- Отзыв разрешения на взлёт (ОРВД -> дрон)

Action: `revoke_takeoff`

Payload:
```JSON
{
  "drone_id": "DRONE123"
}
```
Response:
```JSON
{
  "status": "landing_required",
  "drone_id": "DRONE123",
  "from": "orvd_component"
}
```

- Отправка телеметрии (дрон -> ОРВД)

Action: `send_telemetry`

Payload:
```JSON
{
  "drone_id": "DRONE123",
  "coords": {"lat": 55.7559, "lon": 37.6175},
  "altitude": 120,
  "speed": 10
}
```
Response:

Если всё нормально:
```JSON
{
  "status": "telemetry_received",
  "from": "orvd_component"
}
```
Если дрон вошёл в запретную зону:
```JSON
{
  "status": "emergency",
  "command": "LAND",
  "reason": "entered no_fly_zone",
  "from": "orvd_component"
}
```

- Запрос телеметрии дрона (ОРВД -> дрон)

Action: `request_telemetry`

Payload:
```JSON
{
  "drone_id": "DRONE123",
  "drone_topic": "v1.Agrodron.Agrodron001.navigation"
}
```

Response:

Если телеметрия успешно получена и дрон в безопасной зоне:

```JSON
{
  "status": "telemetry_ok",
  "coords": {"lat":55.4434, "lon": 34.4223},
  "from": "orvd_component"
}
```

Если дрон вошел в запретную зону:

```JSON
- Отправка телеметрии (дрон -> ОРВД)

Action: `send_telemetry`

Payload:
```JSON
{
  "drone_id": "DRONE123",
  "coords": {"lat": 55.7559, "lon": 37.6175},
  "altitude": 120,
  "speed": 10
}
```
Response:

Если всё нормально:
```JSON
{
  "status": "telemetry_received",
  "from": "orvd_component"
}
```
Если дрон вошёл в запретную зону:
```JSON
{
  "status": "emergency",
  "command": "LAND",
  "reason": "entered no_fly_zone",
  "from": "orvd_component"
}
```
Если `drone_id` не указан:

```JSON
{
  "status": "error",
  "message": "drone_id required"
}
```

Если телеметрия не получена в течение таймаута:

```JSON
{
  "status": "error",
  "message": "telemetry_timeout"
}
```

- Добавление запретной зоны (ОРВД)

Action: `add_no_fly_zone`

Payload:
```JSON
{
  "zone_id": "zone1",
  "type": "no_fly",
  "bounds": {
    "min_lat": 55.7550,
    "max_lat": 55.7565,
    "min_lon": 37.6160,
    "max_lon": 37.6180
  },
  "active": true
}
```
Response:
```JSON
{
  "status": "zone_added",
  "zone_id": "zone1"
}
```

- Удаление запретной зоны (ОРВД)

Action: `remove_no_fly_zone`

Payload:
```JSON
{
  "zone_id": "zone1"
}
```
Response:
```JSON
{
  "status": "zone_removed",
  "zone_id": "zone1"
}
```

- Получение истории событий (ОРВД)

Action: `get_history`

Payload: {}

Response:
```JSON
{
  "history": [
    {"event": "drone_registered", "timestamp": "...", "drone_id": "DRONE123"},
    {"event": "mission_registered", "timestamp": "...", "mission_id": 101, "drone_id": "DRONE123"}
  ],
  "from": "orvd_component"
}
```