# API внешних систем

## Топики и формат

**Компоненты дрона** используют схему `v1.{SystemName}.{InstanceID}.{component}` (например `v1.Agrodron.Agrodron001.mission_handler`). Задаётся через `TOPIC_VERSION`, `SYSTEM_NAME`, `INSTANCE_ID`.

**Внешние системы** подключаются **не** по этой схеме: их адреса в брокере — произвольные строки из `agrodron/.env`. В репозитории заданы такие значения по умолчанию:

| Переменная | Пример значения в `agrodron/.env` |
|------------|-----------------------------------|
| `NUS_TOPIC` | `v1.gcs.1.drone_manager` |
| `ORVD_TOPIC` | `v1.ORVD.ORVD001.main` |
| `DRONEPORT_TOPIC` | `v1.drone_port.1.drone_manager` |
| `SITL_TOPIC` | `v1.SITL.SITL001.main` |

**Низкоуровневые каналы SITL** (без обёртки `action` в теле сообщения) задаются отдельно:

| Переменная | Пример |
|------------|--------|
| `SITL_COMMANDS_TOPIC` | `sitl.commands` |
| `SITL_TELEMETRY_REQUEST_TOPIC` | `sitl.telemetry.request` |

Все JSON-сообщения с полем `action` используют структуру:

```json
{
  "action": "<имя_действия>",
  "sender": "<полный_топик_отправителя>",
  "payload": { ... }
}
```

### Доступ внешних систем к компонентам дрона

Компоненты принимают сообщения **только** от монитора безопасности (`sender` = топик `…security_monitor`). Поэтому НУС и ОРВД не публикуют в топик `mission_handler` напрямую: они отправляют **`proxy_request`** (или при необходимости `proxy_publish`) **на топик монитора** `v1.Agrodron.Agrodron001.security_monitor`. В поле `sender` у этого запроса указывается **топик внешней системы** (например `v1.gcs.1.drone_manager`). Монитор проверяет политику `(sender, topic_цели, action)` и проксирует к компоненту.

Исходящие сообщения дрона к внешним системам тоже идут **через монитор** (`proxy_request` / `proxy_publish` с `sender` = топик компонента-инициатора, например автопилота); до внешнего потребителя сообщение доходит с `sender` = топик монитора безопасности.

---

## НУС (Наземная Управляющая Система)

**Топик**: значение `NUS_TOPIC` (в репозитории: `v1.gcs.1.drone_manager`).

### Действия НУС → дрон

Запросы выполняются через **proxy_request** на топик `v1.Agrodron.Agrodron001.security_monitor`. В политиках должны быть разрешены, например:

- `(NUS_TOPIC, v1.Agrodron.Agrodron001.mission_handler, load_mission)`
- `(NUS_TOPIC, v1.Agrodron.Agrodron001.mission_handler, validate_only)`
- `(NUS_TOPIC, v1.Agrodron.Agrodron001.autopilot, cmd)`
- `(NUS_TOPIC, v1.Agrodron.Agrodron001.telemetry, get_state)` — агрегат телеметрии (в т.ч. навигация)

#### get_state (telemetry)

Снимок с борта: motors, sprayer, **navigation** (последние закэшированные `get_state` с компонентов). Запрос — `proxy_request` на монитор, цель `…telemetry`, `action` `get_state`, `data`: `{}`.

#### load_mission

Загрузка миссии в mission_handler. Формат данных — WPL (QGC WPL 110).

Пример сообщения **на монитор безопасности** (внешний клиент подставляет свой `NUS_TOPIC`):

```json
{
  "action": "proxy_request",
  "sender": "v1.gcs.1.drone_manager",
  "payload": {
    "target": {
      "topic": "v1.Agrodron.Agrodron001.mission_handler",
      "action": "load_mission"
    },
    "data": {
      "wpl_content": "QGC WPL 110\n0\t1\t0\t16\t0\t0\t0\t0\t60.0\t30.0\t5.0\t1",
      "mission_id": "mission-001"
    }
  }
}
```

Ответ приходит в обёртке `target_response` от монитора; у mission_handler: `{ "ok": true }` или `{ "ok": false, "error": "wpl_parse_failed" }` (и другие коды ошибок).

#### validate_only

Проверка миссии без загрузки — тот же `proxy_request`, `action` цели `validate_only`, в `data` — `wpl_content`.

#### cmd (start)

Команда запуска выполнения загруженной миссии — цель `autopilot`, действие `cmd`:

```json
{
  "action": "proxy_request",
  "sender": "v1.gcs.1.drone_manager",
  "payload": {
    "target": {
      "topic": "v1.Agrodron.Agrodron001.autopilot",
      "action": "cmd"
    },
    "data": {
      "command": "START"
    }
  }
}
```

Ответ при успехе:

```json
{ "ok": true, "state": "EXECUTING" }
```

Ответ при отказе ОРВД:

```json
{ "ok": false, "error": "orvd_departure_denied" }
```

Ответ при отказе Дронопорта:

```json
{ "ok": false, "error": "droneport_takeoff_denied" }
```

### Действия дрон → НУС

#### mission_status

Уведомление о статусе миссии. Публикуется в сторону топика **`NUS_TOPIC`** через монитор; у внешнего потребителя в сообщении `sender` будет топик монитора безопасности.

Топик назначения: `NUS_TOPIC` (пример: `v1.gcs.1.drone_manager`).

```json
{
  "action": "mission_status",
  "sender": "v1.Agrodron.Agrodron001.security_monitor",
  "payload": {
    "event": "mission_completed",
    "mission_id": "mission-001"
  }
}
```

Возможные события в `payload` (поле `event` и сопутствующие поля):

- `mission_completed` — миссия завершена (`mission_id` и др.)
- `mission_rejected` — отказ до старта (например `reason`: `orvd_denied`, `droneport_denied`, плюс `mission_id`)

---

## ОРВД (Организация Воздушного Движения)

**Топик**: `ORVD_TOPIC` (в репозитории: `v1.ORVD.ORVD001.main`).

Для стенда без реального сервиса на `ORVD_TOPIC` в автопилоте можно включить **`AUTOPILOT_ORVD_MOCK_SUCCESS`** (`1`, `true`, `yes` или `on`): запрос `request_takeoff` по шине **не выполняется**, автопилот считает, что получен ответ **`takeoff_authorized`**, в журнал уходит `ORVD_TAKEOFF_APPROVED` с полями `stub: true` и `reason: AUTOPILOT_ORVD_MOCK_SUCCESS`. В `agrodron/docker-compose.yml` переменная пробрасывается как `AUTOPILOT_ORVD_MOCK_SUCCESS` (источник в merged `.env`: `AUTOPILOT_AUTOPILOT_ORVD_MOCK_SUCCESS`).

### Действия дрон → ОРВД

Автопилот вызывает внешний топик через `proxy_request` на мониторе; пример тела для стороны ОРВД:

#### request_takeoff

```json
{
  "action": "request_takeoff",
  "sender": "v1.Agrodron.Agrodron001.security_monitor",
  "payload": {
    "drone_id": "Agrodron001",
    "mission_id": "mission-001",
    "time": "2026-03-18T12:00:00Z"
  }
}
```

`drone_id` в коде берётся из `INSTANCE_ID` системы (см. `agrodron/.env`).

Ожидаемый ответ:

```json
{ "status": "takeoff_authorized" }
```

или

```json
{ "status": "rejected", "reason": "airspace_restricted" }
```

### Действия ОРВД → дрон

ОРВД может загружать миссии напрямую (аналогично НУС): через **`proxy_request`** на монитор с `sender` = `ORVD_TOPIC` и целью `mission_handler` (`load_mission` / `validate_only`). Политика должна разрешать соответствующие тройки.

#### telemetry (get_state) и команды автопилота (cmd)

Политики также могут разрешать:

- `(ORVD_TOPIC, …telemetry, get_state)` — агрегированная телеметрия (motors, sprayer, **navigation**);
- `(ORVD_TOPIC, …autopilot, cmd)` — команды автопилота (`START`, `PAUSE`, `ABORT`, …), по тому же принципу, что и для НУС.

---

## Дронопорт

**Топик**: `DRONEPORT_TOPIC` — компонент **drone_manager** DronePort (в репозитории интеграции: `v1.drone_port.1.drone_manager`). Имена действий совпадают с `DroneManager` в DronePortGCS.

Без реального сервиса на `DRONEPORT_TOPIC` в автопилоте можно включить **`AUTOPILOT_DRONEPORT_MOCK_SUCCESS`** (`1`, `true`, `yes` или `on`): запросы **`request_takeoff`**, **`request_landing`** и **`request_charging`** по шине **не выполняются**; для взлёта в журнал пишется `DRONEPORT_TAKEOFF_APPROVED` с `stub: true` и `reason: AUTOPILOT_DRONEPORT_MOCK_SUCCESS`. В compose: `AUTOPILOT_DRONEPORT_MOCK_SUCCESS` (merged: `AUTOPILOT_AUTOPILOT_DRONEPORT_MOCK_SUCCESS`).

### Действия дрон → Дронопорт (через МБ: `proxy_request`)

#### request_takeoff

Запрос на взлёт / выезд с порта (после разрешения ОРВД).

```json
{
  "action": "request_takeoff",
  "sender": "v1.Agrodron.Agrodron001.security_monitor",
  "payload": {
    "drone_id": "Agrodron001",
    "battery": 95.0
  }
}
```

`drone_id` совпадает с `INSTANCE_ID` системы дрона (см. `orvd_drone_id()` / `INSTANCE_ID`). Поле **`battery`** (проценты) передаёт актуальный заряд с борта: DronePort иначе берёт значение только из Redis и при пороге **> 80** может отказать (`Not enough battery for takeoff`), если в реестре устаревшие или «unknown» данные. Если в навигации нет батареи, автопилот подставляет `DRONEPORT_TAKEOFF_BATTERY_DEFAULT` (по умолчанию 95).

Успешный ответ (пример):

```json
{
  "battery": 95.0,
  "port_id": "port-1",
  "port_coordinates": { "lat": "60.0", "lon": "30.0" },
  "from": "v1.drone_port.1.drone_manager"
}
```

Отказ:

```json
{
  "error": "Not enough battery for takeoff",
  "from": "v1.drone_port.1.drone_manager"
}
```

#### request_landing

Запрос посадки и назначения порта.

```json
{
  "action": "request_landing",
  "sender": "v1.Agrodron.Agrodron001.security_monitor",
  "payload": {
    "drone_id": "Agrodron001",
    "model": "agrodron"
  }
}
```

`model` задаётся переменной `DRONEPORT_DRONE_MODEL` (по умолчанию `agrodron`).

Успех: в ответе есть `port_id`. Отказ: поле `error` (например нет свободных портов).

#### request_charging

Запрос зарядки на порту (после завершения миссии / посадки).

```json
{
  "action": "request_charging",
  "sender": "v1.Agrodron.Agrodron001.security_monitor",
  "payload": {
    "drone_id": "Agrodron001",
    "battery": 42.0
  }
}
```

Уровень заряда берётся из навигации (`battery_pct` / `battery`), иначе — `DRONEPORT_CHARGING_BATTERY_DEFAULT` (по умолчанию 50). Синхронного ответа от DronePort для этого действия может не быть.

---

## SITL (Симулятор / Цифровой двойник)

### Логический топик адаптера

**`SITL_TOPIC`** — точка для сообщений с полями `action` / `sender` / `payload` (например `set_home` из mission_handler). В репозитории: `v1.SITL.SITL001.main`.

### RAW-протокол

Каналы **`SITL_COMMANDS_TOPIC`** и **`SITL_TELEMETRY_REQUEST_TOPIC`** используют **RAW**-режим: тело сообщения **без** обёртки `{action, sender, payload}`.

Reply/response делается через `reply_to` + `correlation_id`, которые добавляет клиент (в т.ч. `SystemBus.request()` внутри security_monitor).

### Топики

- **Команды приводов**: `sitl.commands` (`SITL_COMMANDS_TOPIC`)
- **Запрос навигации/телеметрии**: `sitl.telemetry.request` (`SITL_TELEMETRY_REQUEST_TOPIC`)

### Действия дрон → SITL

#### Команды приводов (motors → SITL)

От компонента motors через монитор с действием цели `__raw__`. Пример полезной нагрузки:

```json
{
  "drone_id": "drone_001",
  "vx": 1.5,
  "vy": 0.0,
  "vz": 0.0,
  "mag_heading": 90.0
}
```

#### set_home

Установка домашней точки (mission_handler при загрузке миссии). Целевой топик — **`SITL_TOPIC`**, действие `set_home` (после проксирования МБ `sender` у приёмника — топик монитора):

```json
{
  "action": "set_home",
  "sender": "v1.Agrodron.Agrodron001.security_monitor",
  "payload": {
    "drone_id": "drone_001",
    "derived": {
      "lat_decimal": 60.0,
      "lon_decimal": 30.0,
      "altitude_msl": 5.0,
      "gps_valid": true
    }
  }
}
```

**SITL-module (verifier)** в репозитории слушает не `SITL_TOPIC`, а **`SITL_VERIFIER_HOME_TOPIC`** (по умолчанию `sitl-drone-home`) и схему `sitl-drone-home.json`: `drone_id`, `home_lat`, `home_lon`, `home_alt`. После загрузки миссии `mission_handler` дополнительно шлёт туда **RAW** (`proxy_publish` с `__raw__`), иначе Redis SITL не получает HOME.

### Действия SITL → дрон

#### Ответ на запрос телеметрии/навигации (SITL → reply_to)

SITL отвечает в `reply_to` и повторяет `correlation_id` из запроса.

```json
{
  "correlation_id": "e2e4f10a-3a7d-4bdb-9b2f-4a3ad4a02d2c",
  "lat": 59.938623,
  "lon": 30.316534,
  "alt": 100.2
}
```

#### Запрос навигации/телеметрии (navigation → SITL)

RAW request в `SITL_TELEMETRY_REQUEST_TOPIC`:

```json
{
  "drone_id": ["drone_001"]
}
```

---

## Последовательность выполнения миссии

```
НУС -> security_monitor : proxy_request -> mission_handler : load_mission (WPL)
НУС -> security_monitor : proxy_request -> autopilot : cmd START
  autopilot -> ОРВД      : request_takeoff
  autopilot -> Дронопорт : request_takeoff
  [при отказе] autopilot -> НУС : mission_status (mission_rejected)
  [при успехе] autopilot выполняет миссию
  [по завершении]
    autopilot -> Дронопорт: request_landing
    autopilot -> motors: land (посадка)
    autopilot: self_diagnostics()
    autopilot -> Дронопорт: request_charging
    autopilot -> НУС: mission_status (mission_completed)
```

(Топики НУС / ОРВД / Дронопорта подставляются из `NUS_TOPIC`, `ORVD_TOPIC`, `DRONEPORT_TOPIC`.)
