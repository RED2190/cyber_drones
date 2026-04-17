# Политики монитора безопасности (МБ)

Источник: `systems/agrodron/src/security_monitor/.env`, переменная `SECURITY_POLICIES`.
После `make prepare` значение попадает в `systems/agrodron/.generated/.env` как `SECURITY_MONITOR_SECURITY_POLICIES` с раскрытыми подстановками.

Подстановка **`${SYSTEM_NAME}`** в коде МБ и в `prepare_system` — это **полный префикс топика** `v1.{SYSTEM_NAME}.{INSTANCE_ID}` (функция `topic_prefix()`), а не только короткое имя системы. Иначе в политиках получались строки вида `Agrodron.telemetry` вместо `v1.Agrodron.Agrodron001.telemetry`, и `sender` реальных сообщений не совпадал с таблицей — запросы к telemetry (и снимок в system_monitor) отклонялись или «висели» до таймаута.

Каждая политика — тройка **(sender, topic, action)**: при `proxy_request` / `proxy_publish` монитор разрешает сообщение, если `sender` сообщения, целевой `topic` и `action` совпадают с записью.

Значение **`"*"`** в поле `topic` и/или `action` означает «любой топик» и/или «любое действие» для указанного `sender` (проверка в `_is_allowed`). В исходном `SECURITY_POLICIES` для **`${SYSTEM_NAME}.system_monitor`** задано правило с `"topic": "*", "action": "*"`, чтобы монитор системы мог проксировать запросы ко всем компонентам без добавления отдельной строки на каждую пару топик/действие.

Действия **только на топике самого МБ** (`isolation_start`, админские `set_policy` и т.д.) этим списком не задаются — они обрабатываются в коде монитора отдельно.

### Политики в исходном виде (плейсхолдеры `${…}`)

| № | sender | topic | action |
|---|--------|-------|--------|
| 1 | `${SYSTEM_NAME}.limiter` | `${SYSTEM_NAME}.navigation` | `get_state` |
| 2 | `${SYSTEM_NAME}.limiter` | `${SYSTEM_NAME}.telemetry` | `get_state` |
| 3 | `${SYSTEM_NAME}.limiter` | `${SYSTEM_NAME}.emergensy` | `limiter_event` |
| 4 | `${SYSTEM_NAME}.limiter` | `${SYSTEM_NAME}.journal` | `log_event` |
| 5 | `${SYSTEM_NAME}.mission_handler` | `${SYSTEM_NAME}.autopilot` | `mission_load` |
| 6 | `${SYSTEM_NAME}.mission_handler` | `${SYSTEM_NAME}.limiter` | `mission_load` |
| 7 | `${SYSTEM_NAME}.mission_handler` | `${SYSTEM_NAME}.journal` | `log_event` |
| 8 | `${SYSTEM_NAME}.mission_handler` | `${SITL_TOPIC}` | `set_home` |
| 8b | `${SYSTEM_NAME}.mission_handler` | `${SITL_VERIFIER_HOME_TOPIC}` | `__raw__` |
| 9 | `${SYSTEM_NAME}.autopilot` | `${SYSTEM_NAME}.navigation` | `get_state` |
| 10 | `${SYSTEM_NAME}.autopilot` | `${SYSTEM_NAME}.motors` | `set_target` |
| 11 | `${SYSTEM_NAME}.autopilot` | `${SYSTEM_NAME}.sprayer` | `set_spray` |
| 12 | `${SYSTEM_NAME}.autopilot` | `${SYSTEM_NAME}.journal` | `log_event` |
| 13 | `${SYSTEM_NAME}.autopilot` | `${ORVD_TOPIC}` | `request_takeoff` |
| 14 | `${SYSTEM_NAME}.autopilot` | `${DRONEPORT_TOPIC}` | `request_takeoff` |
| 15 | `${SYSTEM_NAME}.autopilot` | `${DRONEPORT_TOPIC}` | `request_landing` |
| 16 | `${SYSTEM_NAME}.autopilot` | `${DRONEPORT_TOPIC}` | `request_charging` |
| 17 | `${SYSTEM_NAME}.autopilot` | `${NUS_TOPIC}` | `mission_status` |
| 18 | `${SYSTEM_NAME}.navigation` | `${SITL_TELEMETRY_REQUEST_TOPIC}` | `__raw__` |
| 19 | `${SYSTEM_NAME}.navigation` | `${SYSTEM_NAME}.journal` | `log_event` |
| 20 | `${SYSTEM_NAME}.emergensy` | `${SYSTEM_NAME}.motors` | `land` |
| 21 | `${SYSTEM_NAME}.emergensy` | `${SYSTEM_NAME}.sprayer` | `set_spray` |
| 22 | `${SYSTEM_NAME}.emergensy` | `${SYSTEM_NAME}.journal` | `log_event` |
| 23 | `${SYSTEM_NAME}.emergensy` | `${SYSTEM_NAME}.security_monitor` | `isolation_status` |
| 24 | `${SYSTEM_NAME}.telemetry` | `${SYSTEM_NAME}.motors` | `get_state` |
| 25 | `${SYSTEM_NAME}.telemetry` | `${SYSTEM_NAME}.sprayer` | `get_state` |
| 26 | `${SYSTEM_NAME}.telemetry` | `${SYSTEM_NAME}.navigation` | `get_state` |
| 27 | `${SYSTEM_NAME}.sprayer` | `${SYSTEM_NAME}.journal` | `log_event` |
| 28 | `${SYSTEM_NAME}.motors` | `${SITL_COMMANDS_TOPIC}` | `__raw__` |
| 29 | `${NUS_TOPIC}` | `${SYSTEM_NAME}.mission_handler` | `load_mission` |
| 30 | `${NUS_TOPIC}` | `${SYSTEM_NAME}.mission_handler` | `validate_only` |
| 31 | `${NUS_TOPIC}` | `${SYSTEM_NAME}.autopilot` | `cmd` |
| 32 | `${ORVD_TOPIC}` | `${SYSTEM_NAME}.mission_handler` | `load_mission` |
| 33 | `${ORVD_TOPIC}` | `${SYSTEM_NAME}.mission_handler` | `validate_only` |
| 34 | `${NUS_TOPIC}` | `${SYSTEM_NAME}.telemetry` | `get_state` |
| 35 | `${ORVD_TOPIC}` | `${SYSTEM_NAME}.telemetry` | `get_state` |
| 36 | `${ORVD_TOPIC}` | `${SYSTEM_NAME}.autopilot` | `cmd` |

### То же после подстановок (типичный `systems/agrodron/.generated/.env`)

| № | sender | topic | action |
|---|--------|-------|--------|
| 1 | `v1.Agrodron.Agrodron001.limiter` | `v1.Agrodron.Agrodron001.navigation` | `get_state` |
| 2 | `v1.Agrodron.Agrodron001.limiter` | `v1.Agrodron.Agrodron001.telemetry` | `get_state` |
| 3 | `v1.Agrodron.Agrodron001.limiter` | `v1.Agrodron.Agrodron001.emergensy` | `limiter_event` |
| 4 | `v1.Agrodron.Agrodron001.limiter` | `v1.Agrodron.Agrodron001.journal` | `log_event` |
| 5 | `v1.Agrodron.Agrodron001.mission_handler` | `v1.Agrodron.Agrodron001.autopilot` | `mission_load` |
| 6 | `v1.Agrodron.Agrodron001.mission_handler` | `v1.Agrodron.Agrodron001.limiter` | `mission_load` |
| 7 | `v1.Agrodron.Agrodron001.mission_handler` | `v1.Agrodron.Agrodron001.journal` | `log_event` |
| 8 | `v1.Agrodron.Agrodron001.mission_handler` | `v1.SITL.SITL001.main` | `set_home` |
| 9 | `v1.Agrodron.Agrodron001.autopilot` | `v1.Agrodron.Agrodron001.navigation` | `get_state` |
| 10 | `v1.Agrodron.Agrodron001.autopilot` | `v1.Agrodron.Agrodron001.motors` | `set_target` |
| 11 | `v1.Agrodron.Agrodron001.autopilot` | `v1.Agrodron.Agrodron001.sprayer` | `set_spray` |
| 12 | `v1.Agrodron.Agrodron001.autopilot` | `v1.Agrodron.Agrodron001.journal` | `log_event` |
| 13 | `v1.Agrodron.Agrodron001.autopilot` | `v1.ORVD.ORVD001.main` | `request_takeoff` |
| 14 | `v1.Agrodron.Agrodron001.autopilot` | `v1.drone_port.1.drone_manager` | `request_takeoff` |
| 15 | `v1.Agrodron.Agrodron001.autopilot` | `v1.drone_port.1.drone_manager` | `request_landing` |
| 16 | `v1.Agrodron.Agrodron001.autopilot` | `v1.drone_port.1.drone_manager` | `request_charging` |
| 17 | `v1.Agrodron.Agrodron001.autopilot` | `v1.gcs.1.drone_manager` | `mission_status` |
| 18 | `v1.Agrodron.Agrodron001.navigation` | `sitl.telemetry.request` | `__raw__` |
| 19 | `v1.Agrodron.Agrodron001.navigation` | `v1.Agrodron.Agrodron001.journal` | `log_event` |
| 20 | `v1.Agrodron.Agrodron001.emergensy` | `v1.Agrodron.Agrodron001.motors` | `land` |
| 21 | `v1.Agrodron.Agrodron001.emergensy` | `v1.Agrodron.Agrodron001.sprayer` | `set_spray` |
| 22 | `v1.Agrodron.Agrodron001.emergensy` | `v1.Agrodron.Agrodron001.journal` | `log_event` |
| 23 | `v1.Agrodron.Agrodron001.emergensy` | `v1.Agrodron.Agrodron001.security_monitor` | `isolation_status` |
| 24 | `v1.Agrodron.Agrodron001.telemetry` | `v1.Agrodron.Agrodron001.motors` | `get_state` |
| 25 | `v1.Agrodron.Agrodron001.telemetry` | `v1.Agrodron.Agrodron001.sprayer` | `get_state` |
| 26 | `v1.Agrodron.Agrodron001.telemetry` | `v1.Agrodron.Agrodron001.navigation` | `get_state` |
| 27 | `v1.Agrodron.Agrodron001.sprayer` | `v1.Agrodron.Agrodron001.journal` | `log_event` |
| 28 | `v1.Agrodron.Agrodron001.motors` | `sitl.commands` | `__raw__` |
| 29 | `v1.gcs.1.drone_manager` | `v1.Agrodron.Agrodron001.mission_handler` | `load_mission` |
| 30 | `v1.gcs.1.drone_manager` | `v1.Agrodron.Agrodron001.mission_handler` | `validate_only` |
| 31 | `v1.gcs.1.drone_manager` | `v1.Agrodron.Agrodron001.autopilot` | `cmd` |
| 32 | `v1.ORVD.ORVD001.main` | `v1.Agrodron.Agrodron001.mission_handler` | `load_mission` |
| 33 | `v1.ORVD.ORVD001.main` | `v1.Agrodron.Agrodron001.mission_handler` | `validate_only` |

## JSON (исходный массив)

```json
[
  {
    "sender": "${SYSTEM_NAME}.limiter",
    "topic": "${SYSTEM_NAME}.navigation",
    "action": "get_state"
  },
  {
    "sender": "${SYSTEM_NAME}.limiter",
    "topic": "${SYSTEM_NAME}.telemetry",
    "action": "get_state"
  },
  {
    "sender": "${SYSTEM_NAME}.limiter",
    "topic": "${SYSTEM_NAME}.emergensy",
    "action": "limiter_event"
  },
  {
    "sender": "${SYSTEM_NAME}.limiter",
    "topic": "${SYSTEM_NAME}.journal",
    "action": "log_event"
  },
  {
    "sender": "${SYSTEM_NAME}.mission_handler",
    "topic": "${SYSTEM_NAME}.autopilot",
    "action": "mission_load"
  },
  {
    "sender": "${SYSTEM_NAME}.mission_handler",
    "topic": "${SYSTEM_NAME}.limiter",
    "action": "mission_load"
  },
  {
    "sender": "${SYSTEM_NAME}.mission_handler",
    "topic": "${SYSTEM_NAME}.journal",
    "action": "log_event"
  },
  {
    "sender": "${SYSTEM_NAME}.mission_handler",
    "topic": "${SITL_TOPIC}",
    "action": "set_home"
  },
  {
    "sender": "${SYSTEM_NAME}.mission_handler",
    "topic": "${SITL_VERIFIER_HOME_TOPIC}",
    "action": "__raw__"
  },
  {
    "sender": "${SYSTEM_NAME}.autopilot",
    "topic": "${SYSTEM_NAME}.navigation",
    "action": "get_state"
  },
  {
    "sender": "${SYSTEM_NAME}.autopilot",
    "topic": "${SYSTEM_NAME}.motors",
    "action": "set_target"
  },
  {
    "sender": "${SYSTEM_NAME}.autopilot",
    "topic": "${SYSTEM_NAME}.sprayer",
    "action": "set_spray"
  },
  {
    "sender": "${SYSTEM_NAME}.autopilot",
    "topic": "${SYSTEM_NAME}.journal",
    "action": "log_event"
  },
  {
    "sender": "${SYSTEM_NAME}.autopilot",
    "topic": "${ORVD_TOPIC}",
    "action": "request_takeoff"
  },
  {
    "sender": "${SYSTEM_NAME}.autopilot",
    "topic": "${DRONEPORT_TOPIC}",
    "action": "request_takeoff"
  },
  {
    "sender": "${SYSTEM_NAME}.autopilot",
    "topic": "${DRONEPORT_TOPIC}",
    "action": "request_landing"
  },
  {
    "sender": "${SYSTEM_NAME}.autopilot",
    "topic": "${DRONEPORT_TOPIC}",
    "action": "request_charging"
  },
  {
    "sender": "${SYSTEM_NAME}.autopilot",
    "topic": "${NUS_TOPIC}",
    "action": "mission_status"
  },
  {
    "sender": "${SYSTEM_NAME}.navigation",
    "topic": "${SITL_TELEMETRY_REQUEST_TOPIC}",
    "action": "__raw__"
  },
  {
    "sender": "${SYSTEM_NAME}.navigation",
    "topic": "${SYSTEM_NAME}.journal",
    "action": "log_event"
  },
  {
    "sender": "${SYSTEM_NAME}.emergensy",
    "topic": "${SYSTEM_NAME}.motors",
    "action": "land"
  },
  {
    "sender": "${SYSTEM_NAME}.emergensy",
    "topic": "${SYSTEM_NAME}.sprayer",
    "action": "set_spray"
  },
  {
    "sender": "${SYSTEM_NAME}.emergensy",
    "topic": "${SYSTEM_NAME}.journal",
    "action": "log_event"
  },
  {
    "sender": "${SYSTEM_NAME}.emergensy",
    "topic": "${SYSTEM_NAME}.security_monitor",
    "action": "isolation_status"
  },
  {
    "sender": "${SYSTEM_NAME}.telemetry",
    "topic": "${SYSTEM_NAME}.motors",
    "action": "get_state"
  },
  {
    "sender": "${SYSTEM_NAME}.telemetry",
    "topic": "${SYSTEM_NAME}.sprayer",
    "action": "get_state"
  },
  {
    "sender": "${SYSTEM_NAME}.telemetry",
    "topic": "${SYSTEM_NAME}.navigation",
    "action": "get_state"
  },
  {
    "sender": "${SYSTEM_NAME}.sprayer",
    "topic": "${SYSTEM_NAME}.journal",
    "action": "log_event"
  },
  {
    "sender": "${SYSTEM_NAME}.motors",
    "topic": "${SITL_COMMANDS_TOPIC}",
    "action": "__raw__"
  },
  {
    "sender": "${NUS_TOPIC}",
    "topic": "${SYSTEM_NAME}.mission_handler",
    "action": "load_mission"
  },
  {
    "sender": "${NUS_TOPIC}",
    "topic": "${SYSTEM_NAME}.mission_handler",
    "action": "validate_only"
  },
  {
    "sender": "${NUS_TOPIC}",
    "topic": "${SYSTEM_NAME}.autopilot",
    "action": "cmd"
  },
  {
    "sender": "${ORVD_TOPIC}",
    "topic": "${SYSTEM_NAME}.mission_handler",
    "action": "load_mission"
  },
  {
    "sender": "${ORVD_TOPIC}",
    "topic": "${SYSTEM_NAME}.mission_handler",
    "action": "validate_only"
  },
  {
    "sender": "${NUS_TOPIC}",
    "topic": "${SYSTEM_NAME}.telemetry",
    "action": "get_state"
  },
  {
    "sender": "${ORVD_TOPIC}",
    "topic": "${SYSTEM_NAME}.telemetry",
    "action": "get_state"
  },
  {
    "sender": "${ORVD_TOPIC}",
    "topic": "${SYSTEM_NAME}.autopilot",
    "action": "cmd"
  }
]
```

## JSON (раскрытый)

```json
[
  {
    "sender": "v1.Agrodron.Agrodron001.limiter",
    "topic": "v1.Agrodron.Agrodron001.navigation",
    "action": "get_state"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.limiter",
    "topic": "v1.Agrodron.Agrodron001.telemetry",
    "action": "get_state"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.limiter",
    "topic": "v1.Agrodron.Agrodron001.emergensy",
    "action": "limiter_event"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.limiter",
    "topic": "v1.Agrodron.Agrodron001.journal",
    "action": "log_event"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.mission_handler",
    "topic": "v1.Agrodron.Agrodron001.autopilot",
    "action": "mission_load"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.mission_handler",
    "topic": "v1.Agrodron.Agrodron001.limiter",
    "action": "mission_load"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.mission_handler",
    "topic": "v1.Agrodron.Agrodron001.journal",
    "action": "log_event"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.mission_handler",
    "topic": "v1.SITL.SITL001.main",
    "action": "set_home"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.autopilot",
    "topic": "v1.Agrodron.Agrodron001.navigation",
    "action": "get_state"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.autopilot",
    "topic": "v1.Agrodron.Agrodron001.motors",
    "action": "set_target"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.autopilot",
    "topic": "v1.Agrodron.Agrodron001.sprayer",
    "action": "set_spray"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.autopilot",
    "topic": "v1.Agrodron.Agrodron001.journal",
    "action": "log_event"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.autopilot",
    "topic": "v1.ORVD.ORVD001.main",
    "action": "request_takeoff"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.autopilot",
    "topic": "v1.drone_port.1.drone_manager",
    "action": "request_takeoff"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.autopilot",
    "topic": "v1.drone_port.1.drone_manager",
    "action": "request_landing"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.autopilot",
    "topic": "v1.drone_port.1.drone_manager",
    "action": "request_charging"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.autopilot",
    "topic": "v1.gcs.1.drone_manager",
    "action": "mission_status"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.navigation",
    "topic": "sitl.telemetry.request",
    "action": "__raw__"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.navigation",
    "topic": "v1.Agrodron.Agrodron001.journal",
    "action": "log_event"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.emergensy",
    "topic": "v1.Agrodron.Agrodron001.motors",
    "action": "land"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.emergensy",
    "topic": "v1.Agrodron.Agrodron001.sprayer",
    "action": "set_spray"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.emergensy",
    "topic": "v1.Agrodron.Agrodron001.journal",
    "action": "log_event"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.emergensy",
    "topic": "v1.Agrodron.Agrodron001.security_monitor",
    "action": "isolation_status"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.telemetry",
    "topic": "v1.Agrodron.Agrodron001.motors",
    "action": "get_state"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.telemetry",
    "topic": "v1.Agrodron.Agrodron001.sprayer",
    "action": "get_state"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.telemetry",
    "topic": "v1.Agrodron.Agrodron001.navigation",
    "action": "get_state"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.sprayer",
    "topic": "v1.Agrodron.Agrodron001.journal",
    "action": "log_event"
  },
  {
    "sender": "v1.Agrodron.Agrodron001.motors",
    "topic": "sitl.commands",
    "action": "__raw__"
  },
  {
    "sender": "v1.gcs.1.drone_manager",
    "topic": "v1.Agrodron.Agrodron001.mission_handler",
    "action": "load_mission"
  },
  {
    "sender": "v1.gcs.1.drone_manager",
    "topic": "v1.Agrodron.Agrodron001.mission_handler",
    "action": "validate_only"
  },
  {
    "sender": "v1.gcs.1.drone_manager",
    "topic": "v1.Agrodron.Agrodron001.autopilot",
    "action": "cmd"
  },
  {
    "sender": "v1.ORVD.ORVD001.main",
    "topic": "v1.Agrodron.Agrodron001.mission_handler",
    "action": "load_mission"
  },
  {
    "sender": "v1.ORVD.ORVD001.main",
    "topic": "v1.Agrodron.Agrodron001.mission_handler",
    "action": "validate_only"
  }
]
```