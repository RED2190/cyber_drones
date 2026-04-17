# Система AgroDron

## 1. Обзор

**AgroDron** — система управления сельскохозяйственным дроном. Все компоненты общаются исключительно через **монитор безопасности (МБ)** — прямой обмен между компонентами запрещён. МБ проверяет каждое сообщение по таблице политик `(sender, topic, action)` и проксирует разрешённые.

### Формат топиков

```
v1.{SystemName}.{InstanceID}.{component}
```

Пример: `v1.Agrodron.Agrodron001.autopilot`

Параметры задаются через переменные окружения: `TOPIC_VERSION`, `SYSTEM_NAME`, `INSTANCE_ID`.

### Формат сообщений

```json
{
  "action": "имя_действия",
  "sender": "полный_топик_отправителя",
  "payload": { },
  "correlation_id": "uuid (для request/response)",
  "reply_to": "топик_для_ответа (для request/response)"
}
```

Поле `sender` содержит полный топик отправителя, например `v1.Agrodron.Agrodron001.autopilot`. Все действия — **lowercase**.

---

## 2. Компоненты

| Компонент | Топик | Назначение |
|---|---|---|
| security_monitor | `…security_monitor` | Шлюз безопасности: проксирует запросы по политикам |
| autopilot | `…autopilot` | Хранение миссии, расчёт управления, взаимодействие с ОРВД/Дронопорт/НУС |
| mission_handler | `…mission_handler` | Загрузка WPL-миссий, валидация, передача в autopilot |
| navigation | `…navigation` | Получение навигации от SITL, нормализация, выдача по запросу |
| motors | `…motors` | Приводы: приём set_target/land, публикация команд в SITL |
| sprayer | `…sprayer` | Опрыскиватель: set_spray, учёт состояния |
| limiter | `…limiter` | Контроль отклонений от маршрута, вызов emergensy при срабатывании |
| emergensy | `…emergensy` | Аварийный протокол: land, закрытие sprayer, изоляция |
| telemetry | `…telemetry` | Агрегация состояния motors, sprayer и navigation |
| journal | `…journal` | Логирование событий в NDJSON-файл |

### Внешние системы

Имена топиков задаются в `systems/agrodron/.env` и **не обязаны** следовать схеме `v1.{SystemName}.{InstanceID}.{component}`.

| Система | Пример в репозитории (`systems/agrodron/.env`) | Переменная |
|---|---|---|
| НУС (наземная управляющая) | `v1.gcs.1.drone_manager` | `NUS_TOPIC` |
| ОРВД (воздушное движение) | `v1.ORVD.ORVD001.main` | `ORVD_TOPIC` |
| Дронопорт | `v1.drone_port.1.drone_manager` | `DRONEPORT_TOPIC` |
| SITL (адаптер с `action`/`payload`) | `v1.SITL.SITL001.main` | `SITL_TOPIC` |
| SITL RAW (команды приводов) | `sitl.commands` | `SITL_COMMANDS_TOPIC` |
| SITL RAW (запрос телеметрии) | `sitl.telemetry.request` | `SITL_TELEMETRY_REQUEST_TOPIC` |

---

## 3. Монитор безопасности (МБ)

Топик: `v1.Agrodron.Agrodron001.security_monitor`

МБ — единственный компонент, через который проходят все межкомпонентные сообщения. Остальные компоненты принимают сообщения **только** от МБ (проверка `sender == topic security_monitor`).

### Действия МБ

| Action | Тип | Описание |
|---|---|---|
| `proxy_request` | RPC | Проксирование запроса к целевому компоненту с ожиданием ответа |
| `proxy_publish` | fire-and-forget | Проксирование сообщения к целевому компоненту без ответа |
| `set_policy` | admin | Добавить политику (только `POLICY_ADMIN_SENDER`) |
| `remove_policy` | admin | Удалить политику |
| `clear_policies` | admin | Сброс всех политик |
| `list_policies` | admin | Список текущих политик |
| `isolation_start` | emergency | Режим изоляции (аварийный набор политик) |
| `isolation_status` | query | Текущий статус изоляции |

### proxy_request

```json
{
  "action": "proxy_request",
  "sender": "v1.Agrodron.Agrodron001.autopilot",
  "payload": {
    "target": {
      "topic": "v1.Agrodron.Agrodron001.navigation",
      "action": "get_state"
    },
    "data": {}
  }
}
```

Ответ:

```json
{
  "target_topic": "v1.Agrodron.Agrodron001.navigation",
  "target_action": "get_state",
  "target_response": { "nav_state": { "lat": 60.0, "lon": 30.0, "alt_m": 5.0, "..." : "..." } }
}
```

### proxy_publish

```json
{
  "action": "proxy_publish",
  "sender": "v1.Agrodron.Agrodron001.autopilot",
  "payload": {
    "target": {
      "topic": "v1.Agrodron.Agrodron001.motors",
      "action": "set_target"
    },
    "data": { "vx": 0.5, "vy": 0.3, "vz": 0.0 }
  }
}
```

---

## 4. API компонентов

Все запросы к компонентам доставляет МБ. Компонент получает сообщение с `sender` = топик security_monitor.

### 4.1. autopilot

| Action | Описание |
|---|---|
| `mission_load` | Загрузить миссию (от mission_handler) |
| `cmd` | Команда управления: `START`, `PAUSE`, `RESUME`, `ABORT`, `RESET`, `EMERGENCY_STOP`, `KOVER` |
| `get_state` | Текущее состояние автопилота |

`cmd` с `command: "START"` запускает последовательность:
1. Запрос `request_takeoff` к ОРВД (разрешение на взлёт)
2. Запрос `request_takeoff` к Дронопорту (drone_manager DronePort — выезд с порта)
3. При отказе — уведомление `mission_rejected` в НУС
4. При успехе — выполнение миссии
5. По завершении — `request_landing` (с `drone_id` и `model`), самодиагностика, `request_charging`, уведомление `mission_completed` в НУС

Дополнительные команды `cmd`: `PAUSE`, `RESUME`, `ABORT`, `RESET`, `EMERGENCY_STOP`, `KOVER` (посадка «ковром» до земли, затем ожидание).

### 4.2. mission_handler

| Action | Описание |
|---|---|
| `load_mission` | Загрузить миссию в формате WPL (QGC WPL 110) |
| `validate_only` | Валидация WPL без загрузки |
| `get_state` | Текущее состояние обработчика |

Payload `load_mission`:

```json
{
  "wpl_content": "QGC WPL 110\n0\t1\t0\t16\t0\t0\t0\t0\t60.0\t30.0\t5.0\t1",
  "mission_id": "mission-001"
}
```

При успешной загрузке mission_handler автоматически передаёт миссию в autopilot (`mission_load`) и limiter (`mission_load`), а также отправляет `set_home` в SITL.

### 4.3. navigation

| Action | Описание |
|---|---|
| `get_state` | Текущее навигационное состояние (NAV_STATE) |
| `nav_state` | Обновить навигационное состояние |
| `update_config` | Обновить конфигурацию (drone_id и т.п.) |

navigation периодически запрашивает SITL через `proxy_request` на топик `SITL_TELEMETRY_REQUEST_TOPIC` с действием `__raw__` (сырой JSON `{"drone_id": ["…"]}` без поля `action` в теле SITL), нормализует ответ в NAV_STATE и хранит актуальное состояние.

### 4.4. motors

| Action | Описание |
|---|---|
| `set_target` | Целевой вектор скорости (vx, vy, vz) или heading/speed |
| `land` | Аварийная посадка |
| `get_state` | Текущее состояние приводов (mode, last_target, temperature) |

При получении `set_target` или `land` motors публикует в SITL через `proxy_publish` на `SITL_COMMANDS_TOPIC` с действием `__raw__` (JSON с полями `drone_id`, `vx`, `vy`, `vz`, `mag_heading`).

### 4.5. sprayer

| Action | Описание |
|---|---|
| `set_spray` | Вкл/выкл опрыскивание (`payload: { "spray": true }`) |
| `get_state` | Текущее состояние (state, temperature, tank_level) |

### 4.6. limiter

| Action | Описание |
|---|---|
| `mission_load` | Синхронизация миссии с autopilot |
| `nav_state` | Обновление навигации для проверки отклонений |
| `update_config` | Обновление лимитов (max_distance, max_alt_deviation) |
| `get_state` | Текущее состояние (state, violations) |

limiter периодически опрашивает navigation и telemetry. При критическом отклонении от маршрута отправляет `limiter_event` в emergensy.

### 4.7. emergensy

| Action | Описание |
|---|---|
| `limiter_event` | Событие от limiter (авария) |
| `get_state` | Текущее состояние (active) |

При получении `limiter_event` emergensy запускает аварийный протокол:
1. Публикация `isolation_start` **на топик** security_monitor (не через `proxy_publish`; проверка отправителя внутри МБ)
2. `proxy_publish` → sprayer `set_spray` (выкл.)
3. `proxy_publish` → motors `land`
4. `proxy_publish` → journal `log_event`

### 4.8. telemetry

| Action | Описание |
|---|---|
| `get_state` | Агрегат состояния motors + sprayer + navigation |

telemetry периодически опрашивает **motors**, **sprayer** и **navigation** (через МБ `proxy_request` к каждому `get_state`), кэширует результаты в `_last_motors` / `_last_sprayer` / `_last_navigation` и отдаёт снимок по запросу `get_state`. Внешние системы (НУС, ОРВД) могут запрашивать тот же `get_state` на топике telemetry при наличии политики.

### 4.9. journal

| Action | Описание |
|---|---|
| `log_event` | Записать событие в NDJSON-файл |

Payload:

```json
{
  "event": "MISSION_STARTED",
  "source": "autopilot",
  "mission_id": "mission-001",
  "details": {}
}
```

---

## 5. Политики безопасности

Политики задаются JSON-массивом в переменной `SECURITY_POLICIES` (файл `systems/agrodron/src/security_monitor/.env`). Каждая запись — тройка `(sender, topic, action)`, где `sender` и `topic` — **полные строки топиков** в брокере.

В `.env` используются подстановки (их раскрывает `scripts/prepare_system.py` при `make prepare`):

| Плейсхолдер | Становится |
|-------------|------------|
| `${SYSTEM_NAME}` | `v1.{SystemName}.{InstanceID}` (префикс топиков компонентов) |
| `${NUS_TOPIC}`, `${ORVD_TOPIC}`, `${DRONEPORT_TOPIC}`, `${SITL_TOPIC}` | значения из смерженного `.env` |
| `${SITL_COMMANDS_TOPIC}`, `${SITL_TELEMETRY_REQUEST_TOPIC}` | RAW-топики SITL |

Пример внутренней политики:

```json
{"sender": "${SYSTEM_NAME}.autopilot", "topic": "${SYSTEM_NAME}.navigation", "action": "get_state"}
```

После раскрытия:

```json
{"sender": "v1.Agrodron.Agrodron001.autopilot", "topic": "v1.Agrodron.Agrodron001.navigation", "action": "get_state"}
```

**Важно:** `mission_handler` отправляет `set_home` на топик **`${SITL_TOPIC}`** (см. `SITL_TOPIC` в `systems/agrodron/.env`), а не на вымышленный `…sitl` внутри префикса дрона. В политике должна быть тройка `(топик mission_handler, значение SITL_TOPIC, set_home)`.

### Вход снаружи (НУС, ОРВД)

Разрешённые обращения к компонентам дрона через `proxy_request` на монитор (в поле `sender` у запроса — топик внешней системы), например:

- `(NUS_TOPIC, …mission_handler, load_mission)`, `(NUS_TOPIC, …mission_handler, validate_only)`, `(NUS_TOPIC, …autopilot, cmd)`, `(NUS_TOPIC, …telemetry, get_state)`
- `(ORVD_TOPIC, …mission_handler, load_mission)`, `(ORVD_TOPIC, …mission_handler, validate_only)`, `(ORVD_TOPIC, …telemetry, get_state)`, `(ORVD_TOPIC, …autopilot, cmd)`

Полный актуальный список — в `SECURITY_POLICIES` после `make prepare` смотрите в `systems/agrodron/.generated/.env` (переменная `SECURITY_MONITOR_SECURITY_POLICIES`).

### Изоляция

Команда `isolation_start` обрабатывается монитором по **прямому** сообщению на его топик (инициатор — `emergensy`); таблица политик для `proxy_*` на это не распространяется. После срабатывания политики заменяются аварийным набором в коде МБ.

### MQTT: пул потоков для входящих сообщений (`MQTT_BUS_CALLBACK_WORKERS`)

При работе через **MQTT** (`BROKER_TYPE=mqtt`) класс `MQTTSystemBus` (`broker/mqtt/mqtt_system_bus.py`) передаёт входящие сообщения на подписанные топики (в том числе на топик МБ) в пул потоков `ThreadPoolExecutor`. Обработчик `proxy_request` на стороне МБ **блокирует** поток на всё время вложенного `bus.request` к целевому компоненту — до **`SECURITY_MONITOR_PROXY_REQUEST_TIMEOUT_S`** секунд на один такой вызов.

Если **потоков мало**, новые запросы к МБ стоят в **очереди** исполнителя, пока занятые потоки ждут ответов по цепочке proxy. Типичный симптом: **первый** запрос успевает, при росте параллельной нагрузки (telemetry, limiter, `system_monitor` и др.) — периодические **таймауты** у клиентов; у **system_monitor** на дашборде это выглядит как ошибка опроса при **сохранённом** последнем успешном снимке.

| | |
|---|---|
| **Переменная** | `MQTT_BUS_CALLBACK_WORKERS` — число потоков пула (в коде нижняя граница 4). |
| **По умолчанию** | 32 — задано в реализации шины и в общем фрагменте `x-common-env` в `systems/agrodron/docker-compose.yml`. |
| **Где задать** | `systems/agrodron/.env`, после `make prepare` — в `systems/agrodron/.generated/.env`, либо переопределение только для нужных сервисов в compose. |

Увеличение значения снижает риск очередей при многих одновременных `proxy_request`; при необходимости дополнительно поднимайте внешние таймауты клиентов (например `SYSTEM_MONITOR_TELEMETRY_TIMEOUT_S` у system_monitor), но сначала имеет смысл проверить этот параметр.

---

## 6. Конфигурация

### Системный `.env` (systems/agrodron/.env)

```ini
TOPIC_VERSION=v1
SYSTEM_NAME=Agrodron
INSTANCE_ID=Agrodron001

ORVD_TOPIC=v1.ORVD.ORVD001.main
NUS_TOPIC=v1.gcs.1.drone_manager
DRONEPORT_TOPIC=v1.drone_port.1.drone_manager
SITL_TOPIC=v1.SITL.SITL001.main

SITL_COMMANDS_TOPIC=sitl.commands
SITL_TELEMETRY_REQUEST_TOPIC=sitl.telemetry.request

# Только для MQTT: размер пула обработки входящих сообщений (см. раздел «MQTT: пул потоков…» выше).
# MQTT_BUS_CALLBACK_WORKERS=32
```

### Компонентные `.env`

Каждый компонент имеет свой `components/<name>/.env` с параметрами: `COMPONENT_ID`, `BROKER_USER`, `BROKER_PASSWORD`, и компонентно-специфичные настройки (интервалы опроса, таймауты, лимиты).

### Генерация

Скрипт `scripts/prepare_system.py` объединяет брокерный и системный docker-compose, мержит все `.env` файлы и раскрывает подстановки в политиках:

```bash
cd systems/agrodron && make prepare
```

Результат: `systems/agrodron/.generated/docker-compose.yml` и `systems/agrodron/.generated/.env`.

---

## 7. Запуск и проверка

### Тесты (без Docker)

```bash
cd systems/agrodron

make test                # Все тесты (unit + integration)
make unit-test           # 44 unit-теста компонентов
make integration-test    # 12 интеграционных тестов (in-process)
```

### Docker

```bash
cd systems/agrodron

make docker-up           # Собрать и запустить все контейнеры
make docker-ps           # Статус контейнеров
make docker-logs         # Логи всех сервисов
make docker-logs-security_monitor   # Логи конкретного сервиса
make docker-down         # Остановить
```

Переменная `BROKER_TYPE` (по умолчанию `mqtt`) определяет используемый брокер: `mqtt` или `kafka`.

### Полный цикл

```bash
make status              # prepare + test + docker-up + docker-ps
```

### На что смотреть в логах

- Каждый компонент должен вывести: `Started. Listening on topic: v1.Agrodron.Agrodron001.<component>`
- security_monitor логирует загрузку политик и каждый proxy_request/proxy_publish
- Не должно быть сообщений `denied by policy` при штатной работе

---

## 8. Последовательность выполнения миссии

```
НУС -> security_monitor : proxy_request -> mission_handler : load_mission (WPL)
  mission_handler -> autopilot : mission_load
  mission_handler -> limiter   : mission_load
  mission_handler -> SITL_TOPIC (`set_home`, см. `SITL_TOPIC` в `.env`)

НУС -> security_monitor : proxy_request -> autopilot : cmd START
  autopilot -> ОРВД      : request_takeoff
  autopilot -> Дронопорт : request_takeoff
  [при отказе]
    autopilot -> НУС : mission_status (mission_rejected)
  [при успехе]
    autopilot выполняет миссию (цикл: get_state navigation, set_target motors, set_spray sprayer)
  [по завершении]
    autopilot -> Дронопорт : request_landing
    autopilot -> motors    : land
    autopilot : self_diagnostics()
    autopilot -> Дронопорт : request_charging
    autopilot -> НУС       : mission_status (mission_completed)
```

### Аварийный сценарий

```
limiter обнаруживает отклонение от маршрута
  limiter -> emergensy : limiter_event
    emergensy -> security_monitor (топик МБ): isolation_start
    emergensy -> security_monitor : proxy_publish -> sprayer / motors / journal
```

---

## 9. Структура проекта

```
systems/agrodron/
  .env                          Системные параметры (топики, имя системы)
  docker-compose.yml            Сервисы компонентов
  Makefile                      Команды сборки, тестирования, запуска
  .generated/                   Сгенерированные docker-compose.yml и .env
  components/
    autopilot/                  Автопилот
    emergensy/                  Аварийный протокол
    journal/                    Журнал событий
    limiter/                    Контроль отклонений
    mission_handler/            Загрузка миссий (WPL)
    motors/                     Приводы
    navigation/                 Навигация (SITL)
    security_monitor/           Монитор безопасности
    sprayer/                    Опрыскиватель
    telemetry/                  Телеметрия
  tests/
    integration/                Интеграционные тесты (in-process)

sdk/                            BaseComponent, topic_utils
broker/                         SystemBus, MQTTSystemBus, KafkaSystemBus
docker/                         Брокер (Kafka, MQTT), docker-compose
scripts/                        prepare_system.py
config/                         Pipfile, pyproject.toml
docs/
  SYSTEM.md                     Эта документация
  EXTERNAL_API.md               API для внешних систем (НУС, ОРВД, Дронопорт, SITL)
```
