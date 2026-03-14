# Документация системы AgroDron

Руководство по внедрению и API системы управления агродроном.

---

## 1. Обзор системы

**AgroDron** — система управления сельскохозяйственным дроном с симуляцией (SITL). Все компоненты общаются **только через монитор безопасности (МБ)** — прямой обмен между компонентами запрещён.

### 1.1. Компоненты

| Компонент          | Назначение                                                                 |
|--------------------|----------------------------------------------------------------------------|
| security_monitor   | Шлюз безопасности: проксирует запросы по политикам, принимает только от МБ |
| mission_handler    | Загрузка WPL-миссий, передача в autopilot, отправка HOME в SITL            |
| autopilot          | Хранение миссии, расчёт векторов скорости, управление motors/sprayer       |
| navigation         | Чтение навигации из Redis SITL, нормализация, выдача по запросу           |
| motors             | Приводы: приём SET_TARGET/LAND, публикация команд в Kafka SITL            |
| sprayer            | Опрыскиватель: SET_SPRAY, учёт состояния                                  |
| limiter            | Контроль отклонений от маршрута, вызов emergensy при срабатывании         |
| emergensy          | Аварийный протокол: LAND, закрытие sprayer, журналирование                |
| telemetry          | Агрегация состояния motors и sprayer по запросу                           |
| journal            | Логирование событий (ndjson-файл)                                         |

---

## 2. Инфраструктура для внедрения

### 2.1. Требуемые сервисы

- **Kafka** или **MQTT** — брокер сообщений (топики `agrodron.<component>`)
- **Redis** — хранение состояния SITL (ключ `SITL:{drone_id}` или настраиваемый)
- **SITL** — симулятор дрона (Kafka `input-messages`, `sitl-drone-home`)

### 2.2. Подготовка окружения

```bash
# 1. Подготовка системы (создаёт сети, брокер и т.д.)
python scripts/prepare_system.py systems/agrodron

# 2. Запуск компонентов (профиль kafka или mqtt)
docker compose --profile kafka up -d
```

### 2.3. Переменные окружения

Основные переменные для `.env`:

```ini
SYSTEM_NAME=agrodron
BROKER_TYPE=kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:29092
ADMIN_USER=admin
ADMIN_PASSWORD=admin123
DOCKER_NETWORK=drones_net

# SITL
SITL_DRONE_ID=drone_001
SITL_KAFKA_SERVERS=kafka:29092
SITL_KAFKA_COMMANDS_TOPIC=input-messages
SITL_KAFKA_HOME_TOPIC=sitl-drone-home
SITL_REDIS_URL=redis://redis:6379/0
SITL_REDIS_KEY_PREFIX=SITL
```

---

## 3. API монитора безопасности (МБ)

Топик: `agrodron.security_monitor`

Все запросы к другим компонентам идут **через МБ**. Формат сообщений — JSON.

### 3.1. proxy_request (RPC)

Запрос с ожиданием ответа.

**Запрос в МБ:**

```json
{
  "action": "proxy_request",
  "sender": "client_id",
  "payload": {
    "target": {
      "topic": "agrodron.navigation",
      "action": "get_state"
    },
    "data": {}
  }
}
```

**Ответ МБ:**

```json
{
  "target_topic": "agrodron.navigation",
  "target_action": "get_state",
  "target_response": { ... }
}
```

### 3.2. proxy_publish (fire-and-forget)

Команда без ответа.

**Запрос в МБ:**

```json
{
  "action": "proxy_publish",
  "sender": "autopilot",
  "payload": {
    "target": {
      "topic": "agrodron.motors",
      "action": "SET_TARGET"
    },
    "data": {
      "vx": 0.5,
      "vy": 0.3,
      "vz": 0.0,
      "alt_m": 50.0,
      "lat": 60.0,
      "lon": 30.0,
      "heading_deg": 90.0,
      "drop": false
    }
  }
}
```

### 3.3. Административные actions

- `set_policy` — добавить политику (только POLICY_ADMIN_SENDER)
- `remove_policy` — удалить политику
- `clear_policies` — сброс всех политик
- `list_policies` — список текущих политик
- `ISOLATION_START` — режим изоляции (аварийный набор политик)
- `isolation_status` — статус изоляции

---

## 4. API компонентов

Все запросы к компонентам доставляет МБ. В сообщении `sender` = `security_monitor`.

### 4.1. mission_handler

**Топик:** `agrodron.mission_handler`

| Action          | Описание                              |
|-----------------|---------------------------------------|
| `LOAD_MISSION`  | Загрузить WPL и передать в autopilot  |
| `VALIDATE_ONLY` | Только валидация без передачи         |
| `get_state`     | Текущее состояние обработчика         |

**LOAD_MISSION payload:**

```json
{
  "wpl_content": "QGC WPL 110\n0\t1\t0\t16\t0\t0\t0\t0\t60.0\t30.0\t0.0\t1\n...",
  "mission_id": "mission-1"
}
```

**Ответ:** `{"ok": true}` или `{"ok": false, "error": "..."}`

---

### 4.2. autopilot

**Топик:** `agrodron.autopilot`

| Action         | Описание                         |
|----------------|----------------------------------|
| `mission_load` | Загрузить миссию                 |
| `cmd`          | Команда управления               |
| `get_state`    | Текущее состояние автопилота     |

**mission_load payload:**

```json
{
  "mission": {
    "mission_id": "mission-1",
    "steps": [
      {
        "lat": 60.123,
        "lon": 30.456,
        "alt_m": 5.0,
        "speed_mps": 5.0,
        "spray": false
      }
    ]
  }
}
```

**cmd payload:**

```json
{
  "command": "START"   // START | PAUSE | RESUME | ABORT | RESET | EMERGENCY_STOP | KOVER
}
```

**get_state ответ:**

```json
{
  "state": "EXECUTING",
  "mission_id": "mission-1",
  "current_step_index": 2,
  "total_steps": 5,
  "sprayer_state": "ON",
  "last_nav_state": { "lat": 60.0, "lon": 30.0, "alt_m": 50.0, "heading_deg": 90.0 }
}
```

---

### 4.3. navigation

**Топик:** `agrodron.navigation`

| Action          | Описание                            |
|-----------------|-------------------------------------|
| `get_state`     | Текущий NAV_STATE                   |
| `nav_state`     | Обновить nav_state (редко)          |
| `update_config` | Обновить конфиг (drone_id и т.п.)   |

**get_state ответ:**

```json
{
  "nav_state": {
    "lat": 60.0,
    "lon": 30.0,
    "alt_m": 50.0,
    "ground_speed_mps": 5.0,
    "heading_deg": 90.0,
    "gps_valid": true,
    "fix": "3D",
    "satellites": 10,
    "hdop": 0.8,
    "timestamp": "2026-03-13T12:00:00.000Z"
  },
  "config": {},
  "payload": { ... }
}
```

---

### 4.4. motors

**Топик:** `agrodron.motors`

| Action       | Описание                               |
|--------------|----------------------------------------|
| `SET_TARGET` | Целевой вектор (vx, vy, vz) или heading/speed |
| `LAND`       | Аварийная посадка                      |
| `get_state`  | Текущее состояние приводов             |

**SET_TARGET payload:**

```json
{
  "vx": 0.5,
  "vy": 0.3,
  "vz": 0.0,
  "alt_m": 50.0,
  "lat": 60.0,
  "lon": 30.0,
  "heading_deg": 90.0,
  "drop": false
}
```

Альтернативный формат (legacy):

```json
{
  "heading_deg": 90.0,
  "ground_speed_mps": 5.0,
  "alt_m": 50.0
}
```

---

### 4.5. sprayer

**Топик:** `agrodron.sprayer`

| Action      | Описание            |
|-------------|---------------------|
| `SET_SPRAY` | Вкл/выкл опрыскивание |
| `get_state` | Текущее состояние   |

**SET_SPRAY payload:**

```json
{
  "spray": true
}
```

---

### 4.6. limiter

**Топик:** `agrodron.limiter`

| Action         | Описание                          |
|----------------|-----------------------------------|
| `mission_load` | Синхронизация миссии с autopilot  |
| `update_config`| Обновление лимитов               |
| `get_state`    | Текущее состояние                |

---

### 4.7. emergensy

**Топик:** `agrodron.emergensy`

| Action          | Описание                      |
|-----------------|-------------------------------|
| `limiter_event` | Событие от limiter (авария)   |
| `get_state`     | Текущее состояние            |

**limiter_event payload:**

```json
{
  "event": "path_deviation",
  "details": { "distance_m": 15.0, ... }
}
```

---

### 4.8. telemetry

**Топик:** `agrodron.telemetry`

| Action      | Описание                 |
|-------------|--------------------------|
| `get_state` | Агрегат motors + sprayer |

---

### 4.9. journal

**Топик:** `agrodron.journal`

| Action     | Описание         |
|------------|------------------|
| `LOG_EVENT`| Записать событие |

**LOG_EVENT payload:**

```json
{
  "event": "MISSION_STARTED",
  "source": "autopilot",
  "details": { "mission_id": "mission-1" }
}
```

---

## 5. Интеграция с SITL

### 5.1. Исходящие данные (agrodron → SITL)

**Kafka топик `input-messages`** (команды движения):

```json
{
  "drone_id": "drone_001",
  "msg_id": "uuid",
  "timestamp": "2026-03-13T12:00:00.000Z",
  "nmea": {
    "rmc": { "course_degrees": 90.0, "speed_knots": 9.7, "latitude": "...", "longitude": "..." },
    "gga": { "quality": 1, "satellites": 10, "hdop": 0.8 }
  },
  "derived": {
    "lat_decimal": 60.0,
    "lon_decimal": 30.0,
    "altitude_msl": 50.0,
    "speed_vertical_ms": 0.0
  },
  "actions": {
    "drop": false,
    "emergency_landing": false
  }
}
```

**Kafka топик `sitl-drone-home`** (HOME при загрузке миссии):

```json
{
  "drone_id": "drone_001",
  "msg_id": "uuid",
  "timestamp": "2026-03-13T12:00:00.000Z",
  "nmea": { "rmc": {...}, "gga": {...} },
  "derived": {
    "lat_decimal": 60.0,
    "lon_decimal": 30.0,
    "altitude_msl": 0.0,
    "gps_valid": true,
    "satellites_used": 10,
    "position_accuracy_hdop": 0.8
  }
}
```

### 5.2. Входящие данные (SITL → agrodron)

**Redis** — ключ `SITL:{drone_id}` (или настраиваемый префикс). Значение — JSON.

Формат, поддерживаемый `sitl_normalizer`:

```json
{
  "verifier_stage": "SITL-v1",
  "data": {
    "lat": 60.0,
    "lon": 30.0,
    "vx": 0.5,
    "vy": 0.3,
    "heading": 90.0,
    "derived": {
      "lat_decimal": 60.0,
      "lon_decimal": 30.0,
      "altitude_msl": 50.0
    }
  }
}
```

Компонент `navigation` читает Redis с периодом 10 Гц и нормализует данные в NAV_STATE.

---

## 6. Политики доступа (SECURITY_POLICIES)

Политики задаются JSON-массивом. Каждая запись: `(sender, topic, action)`.

Пример минимального набора:

```json
[
  {"sender":"mission_handler","topic":"agrodron.autopilot","action":"mission_load"},
  {"sender":"mission_handler","topic":"agrodron.limiter","action":"mission_load"},
  {"sender":"mission_handler","topic":"agrodron.journal","action":"LOG_EVENT"},
  {"sender":"autopilot","topic":"agrodron.navigation","action":"get_state"},
  {"sender":"autopilot","topic":"agrodron.motors","action":"SET_TARGET"},
  {"sender":"autopilot","topic":"agrodron.sprayer","action":"SET_SPRAY"},
  {"sender":"autopilot","topic":"agrodron.journal","action":"LOG_EVENT"},
  {"sender":"limiter","topic":"agrodron.navigation","action":"get_state"},
  {"sender":"limiter","topic":"agrodron.telemetry","action":"get_state"},
  {"sender":"limiter","topic":"agrodron.emergensy","action":"limiter_event"},
  {"sender":"limiter","topic":"agrodron.journal","action":"LOG_EVENT"},
  {"sender":"navigation","topic":"agrodron.journal","action":"LOG_EVENT"},
  {"sender":"emergensy","topic":"agrodron.motors","action":"LAND"},
  {"sender":"emergensy","topic":"agrodron.sprayer","action":"SET_SPRAY"},
  {"sender":"emergensy","topic":"agrodron.journal","action":"LOG_EVENT"},
  {"sender":"telemetry","topic":"agrodron.motors","action":"get_state"},
  {"sender":"telemetry","topic":"agrodron.sprayer","action":"get_state"},
  {"sender":"sprayer","topic":"agrodron.journal","action":"LOG_EVENT"},
  {"sender":"nsu","topic":"agrodron.mission_handler","action":"LOAD_MISSION"},
  {"sender":"nsu","topic":"agrodron.mission_handler","action":"VALIDATE_ONLY"},
  {"sender":"orvd","topic":"agrodron.mission_handler","action":"LOAD_MISSION"},
  {"sender":"orvd","topic":"agrodron.mission_handler","action":"VALIDATE_ONLY"}
]
```

Подстановка `${SYSTEM_NAME}` в топиках заменяется на `agrodron`.

---

## 7. Типовой сценарий внедрения

1. **Инфраструктура:** поднять Kafka, Redis, SITL в Docker.
2. **Сеть:** создать `drones_net`, подключить все контейнеры.
3. **Конфигурация:** скопировать `.env.example` в `.env`, задать `SECURITY_POLICIES` и параметры SITL.
4. **Запуск:** `docker compose --profile kafka up -d`.
5. **Проверка:** отправить `LOAD_MISSION` через МБ от `nsu`/`orvd`, затем `cmd: START` на autopilot.
6. **Мониторинг:** журнал в `JOURNAL_FILE_PATH`, топик `agrodron.sitl.commands` для наблюдения за командами.

---
