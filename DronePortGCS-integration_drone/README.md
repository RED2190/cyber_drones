# DronePort and GCS

README описывает внешний контракт двух систем в репозитории:

- `DronePort` - сервис наземной инфраструктуры для приема дронов, управления портами и зарядкой.
- `GCS` - НУС для постановки задач дронам, подготовки миссий и передачи полетных команд через брокер сообщений.

Ниже отдельно разобрано, что должен знать интегратор, какие топики используются и какие сообщения реально поддерживаются в текущей реализации.

## Содержание

- [Дронопорт](#дронопорт)
- [GCS](#gcs)
- [Запуск](#запуск)
- [Тесты](#тесты)
- [Структура репозитория](#структура-репозитория)

## Дронопорт

### Назначение

DronePort принимает запросы на посадку, взлет и зарядку, распределяет порты, хранит состояние портов и дронов и, при необходимости, передает состояние дронов Эксплуатанту и SITL.

### Состав DronePort

Система состоит из шести компонентов:

- `orchestrator` - внешняя точка входа для запросов к DronePort от Эксплуатанта.
- `drone_manager` - обработка запросов от Дронов на посадку, взлет и зарядку.
- `drone_registry` - реестр дронов и фасад для чтения их статуса.
- `port_manager` - работа со слотами посадки.
- `charging_manager` - запуск и симуляция зарядки.
- `state_store` - хранение состояния портов в Redis.

### Топики и адресация DronePort

Адресация DronePort задается тремя переменными:

- `TOPIC_VERSION`, по умолчанию `v1`
- `SYSTEM_NAME`, по умолчанию `drone_port`
- `INSTANCE_ID`, по умолчанию `1`

Формула внутренних топиков:

```text
<TOPIC_VERSION>.<SYSTEM_NAME>.<INSTANCE_ID>.<component>
```

При значениях по умолчанию используются такие топики:

| Назначение | Топик |
|------------|-------|
| Эксплуатант -> Orchestrator | `v1.drone_port.1.orchestrator` |
| Дрон -> DroneManager | `v1.drone_port.1.drone_manager` |
| Внутренние запросы -> DroneRegistry | `v1.drone_port.1.registry` |
| Внутренние запросы -> PortManager | `v1.drone_port.1.port_manager` |
| Внутренние запросы -> ChargingManager | `v1.drone_port.1.charging_manager` |
| Внутренние запросы -> StateStore | `v1.drone_port.1.state_store` |

Для внешней интеграции используются две входные точки:

- `v1.drone_port.1.orchestrator` - для запросов от внешней системы эксплуатанта;
- `v1.drone_port.1.drone_manager` - для запросов от самих дронов на посадку, взлет и зарядку.

### Actions DronePort

#### Orchestrator

Топик:

- `v1.drone_port.1.orchestrator`

Поддерживаемые actions:

| Action | Payload | Ответ | Назначение |
|--------|---------|-------|------------|
| `get_available_drones` | `{}` | `{"drones": [...], "from": "orchestrator"}` | Получить список доступных дронов через `drone_registry` |

#### DroneManager

Топик:

- `v1.drone_port.1.drone_manager`

Поддерживаемые actions:

| Action | Payload | Ответ | Назначение |
|--------|---------|-------|------------|
| `request_landing` | `{"drone_id": str, "model": str}` | `{"port_id": str, "from": "drone_manager"}` или `{"error": str, "from": "drone_manager"}` | Назначить свободный порт и зарегистрировать дрон |
| `request_takeoff` | `{"drone_id": str, "battery": float (опционально)}` | `{"battery": float, "port_id": str, "port_coordinates": {"lat": str, "lon": str}, "from": "drone_manager"}` или `{"error": str, "from": "drone_manager"}` | Освободить порт и опубликовать HOME в SITL (`SITL_HOME_TOPIC`, схема verifier). Если `battery` передан — используется для проверки порога >80%; иначе — значение из Redis (`get_drone`). |
| `request_charging` | `{"drone_id": str, "battery": float}` | Нет синхронного ответа | Опубликовать команду старта зарядки в `charging_manager` |

#### DroneRegistry

Топик:

- `v1.drone_port.1.registry`

Поддерживаемые actions:

| Action | Payload | Ответ | Назначение |
|--------|---------|-------|------------|
| `register_drone` | `{"drone_id": str, "model": str}` | Нет синхронного ответа | Сохранить новый дрон в Redis |
| `get_drone` | `{"drone_id": str}` | Данные дрона или `{"error": "Drone not found"}` | Получить запись по конкретному дрону |
| `get_available_drones` | `{}` | `{"drones": [...], "from": "registry"}` | Вернуть дронов в статусе `ready` |
| `delete_drone` | `{"drone_id": str}` | Нет синхронного ответа | Удалить запись дрона |
| `charging_started` | `{"drone_id": str}` | Нет синхронного ответа | Перевести дрон в статус `charging` |
| `update_battery` | `{"drone_id": str, "battery": float}` | Нет синхронного ответа | Обновить заряд и статус дрона |

#### PortManager

Топик:

- `v1.drone_port.1.port_manager`

Поддерживаемые actions:

| Action | Payload | Ответ | Назначение |
|--------|---------|-------|------------|
| `request_landing` | `{"drone_id": str}` | `{"port_id": str}` или `{"error": "No free ports"}` | Найти свободный порт и зарезервировать его |
| `free_slot` | `{"port_id": str}` | Нет синхронного ответа | Освободить порт |
| `get_port_status` | `{}` | `{"ports": [...]}` | Вернуть текущий список портов из `state_store` |

#### ChargingManager

Топик:

- `v1.drone_port.1.charging_manager`

Поддерживаемые actions:

| Action | Payload | Ответ | Назначение |
|--------|---------|-------|------------|
| `start_charging` | `{"drone_id": str, "battery": float}` | Нет синхронного ответа | Опубликовать `charging_started` и начать обновление батареи |

#### StateStore

Топик:

- `v1.drone_port.1.state_store`

Поддерживаемые actions:

| Action | Payload | Ответ | Назначение |
|--------|---------|-------|------------|
| `get_all_ports` | `{}` | `{"ports": [...]}` | Получить все порты со статусом, `drone_id`, `lat`, `lon` |
| `update_port` | `{"port_id": str, "drone_id": str \| null, "status": str}` | Нет синхронного ответа | Обновить запись порта |

Пример ответа `get_all_ports`:

```json
{
  "ports": [
    {
      "port_id": "P-01",
      "drone_id": "",
      "status": "free",
      "lat": "55.751000",
      "lon": "37.617000"
    }
  ]
}
```

## GCS

### Назначение

GCS принимает задачу от внешней системы эксплуатанта, строит маршрут, сохраняет миссию, конвертирует ее в `QGC WPL 110`, назначает миссию на конкретный борт и взаимодействует с дроном:

- загрузить миссию;
- подать команду на старт миссии;
- запросить телеметрию дрона.

### Состав GCS

Система состоит из шести компонентов:

- `orchestrator` - внешняя точка входа для эксплуатанта.
- `path_planner` - строит маршрут по стартовой и конечной точке.
- `mission_store` - хранит миссии в Redis.
- `mission_converter` - преобразует маршрут в `QGC WPL 110`.
- `drone_manager` - публикует команды в текущий stub-канал борта и обновляет состояние миссии/борта.
- `drone_store` - хранит состояние дронов и последнюю телеметрию в Redis.

### Топики и адресация

Адресация GCS задается тремя переменными:

- `TOPIC_VERSION`, по умолчанию `v1`
- `GCS_SYSTEM_NAME`, по умолчанию `gcs`
- `INSTANCE_ID`, по умолчанию `1`

Формула внутренних топиков:

```text
<TOPIC_VERSION>.<GCS_SYSTEM_NAME>.<INSTANCE_ID>.<component>
```

При значениях по умолчанию используются такие топики:

| Назначение | Топик |
|------------|-------|
| Эксплуатант -> Orchestrator | `v1.gcs.1.orchestrator` |
| Внутренние запросы -> PathPlanner | `v1.gcs.1.path_planner` |
| Внутренние запросы -> MissionStore | `v1.gcs.1.mission_store` |
| Внутренние запросы -> MissionConverter | `v1.gcs.1.mission_converter` |
| Дрон -> DroneManager | `v1.gcs.1.drone_manager` |
| Внутренние запросы -> DroneStore | `v1.gcs.1.drone_store` |

Для внешних систем сейчас обычно нужны только:

- `v1.gcs.1.orchestrator`
- `v1.gcs.1.drone_manager`

Топик `drone` в этот список не включен как стабильная точка интеграции, потому что он временный.

### Протокол сообщений

Базовый формат сообщения:

```json
{
  "action": "task.submit",
  "payload": {},
  "sender": "external_system",
  "correlation_id": "corr-123",
  "reply_to": "optional.reply.topic",
  "timestamp": "2026-03-17T10:00:00+00:00"
}
```

Поля:

- `action` - обязательное действие.
- `payload` - обязательный объект с данными.
- `sender` - отправитель.
- `correlation_id` - рекомендован для трассировки цепочки.
- `reply_to` - обязателен только если нужен синхронный ответ.
- `timestamp` - можно не задавать вручную, но для внешних интеграций полезен.

Формат ответа на request:

```json
{
  "action": "response",
  "payload": {},
  "sender": "gcs_orchestrator",
  "correlation_id": "corr-123",
  "success": true,
  "timestamp": "2026-03-17T10:00:01+00:00"
}
```

При ошибке дополнительно приходит поле `error`.

### Интеграция с эксплуатантом

#### 1. Постановка задачи

Топик:

- `v1.gcs.1.orchestrator`

Action:

- `task.submit`

Назначение:

- создать новую миссию;
- построить маршрут;
- сохранить миссию в `mission_store`;
- вернуть `mission_id` и построенный маршрут.

Минимальный запрос:

```json
{
  "action": "task.submit",
  "sender": "operator_system",
  "correlation_id": "corr-submit-001",
  "reply_to": "operator/replies",
  "payload": {
    "task": {
      "waypoints": [
        {"lat": 55.751244, "lon": 37.618423, "alt": 120},
        {"lat": 55.761244, "lon": 37.628423, "alt": 130}
      ]
    }
  }
}
```

Сейчас `path_planner` принимает только `2` или `3` опорные точки в `payload.task.waypoints`.

Успешный ответ:

```json
{
  "action": "response",
  "sender": "gcs_orchestrator",
  "correlation_id": "corr-submit-001",
  "success": true,
  "payload": {
    "from": "gcs_orchestrator",
    "mission_id": "m-abcdef123456",
    "waypoints": [
      {"lat": 55.751244, "lon": 37.618423, "alt": 120.0},
      {"lat": 55.754544, "lon": 37.621723, "alt": 123.3},
      {"lat": 55.757844, "lon": 37.625023, "alt": 126.6},
      {"lat": 55.761244, "lon": 37.628423, "alt": 130.0},
      {"lat": 55.757944, "lon": 37.625123, "alt": 126.7},
      {"lat": 55.754644, "lon": 37.621823, "alt": 123.4},
      {"lat": 55.751244, "lon": 37.618423, "alt": 120.0}
    ]
  }
}
```

Ответ при ошибке:

```json
{
  "action": "response",
  "sender": "gcs_orchestrator",
  "correlation_id": "corr-submit-001",
  "success": true,
  "payload": {
    "from": "gcs_orchestrator",
    "error": "failed to build route"
  }
}
```

Замечание: на уровне бизнес-логики ошибка маршрута сейчас возвращается внутри `payload`, а не через `success=false`.

#### 2. Назначение миссии на дрон

Топик:

- `v1.gcs.1.orchestrator`

Action:

- `task.assign`

Назначение:

- взять уже сохраненную миссию по `mission_id`;
- преобразовать маршрут в `WPL`;
- опубликовать команду загрузки миссии в временный stub-топик `drone`;
- перевести миссию в статус `assigned`;
- перевести дрон в статус `reserved`.

Сообщение:

```json
{
  "action": "task.assign",
  "sender": "operator_system",
  "correlation_id": "corr-assign-001",
  "payload": {
    "mission_id": "m-abcdef123456",
    "drone_id": "drone-01"
  }
}
```

Синхронный ответ не предусмотрен. Подтверждение нужно отслеживать косвенно:

- по сообщению `drone.upload_mission` в stub-топике `drone`;
- по внутреннему состоянию миссии и дрона.

#### 3. Старт миссии

Топик:

- `v1.gcs.1.orchestrator`

Action:

- `task.start`

Назначение:

- отправить дрону команду старта миссии;
- перевести миссию в `running`;
- перевести дрон в `busy`.

Сообщение:

```json
{
  "action": "task.start",
  "sender": "operator_system",
  "correlation_id": "corr-start-001",
  "payload": {
    "mission_id": "m-abcdef123456",
    "drone_id": "drone-01"
  }
}
```

Синхронный ответ не предусмотрен.

### Временный stub-канал дрона

Топик `drone` в текущей реализации используется как заглушка вместо настоящего канала связи с дроном. Этот интерфейс не стоит считать целевым внешним контрактом на будущее: он нужен для текущей разработки, тестов и эмуляции борта.

#### Сообщения, которые GCS публикует в stub-топик

Топик:

- `drone`

##### 1. Загрузка миссии

Action:

- `drone.upload_mission`

Сообщение:

```json
{
  "action": "drone.upload_mission",
  "sender": "gcs_drone_manager",
  "correlation_id": "corr-assign-001",
  "payload": {
    "mission_id": "m-abcdef123456",
    "mission": "QGC WPL 110\n0\t1\t3\t16\t0\t0\t0\t0\t55.751244\t37.618423\t120.0\t1\n1\t0\t3\t16\t0\t0\t0\t0\t55.754544\t37.621723\t123.3\t1"
  }
}
```

Во внутреннем сообщении `mission.upload` между `orchestrator` и `drone_manager` WPL передается в поле `wpl`.
При публикации в stub-топик `drone` этот же WPL уходит наружу в поле `mission`.

Формат строки WPL, который генерирует GCS:

```text
QGC WPL 110
<seq> <current> <frame> <command> <p1> <p2> <p3> <p4> <lat> <lon> <alt> <autocontinue>
```

Сейчас по умолчанию:

- первая точка идет с `current=1`, остальные с `current=0`;
- `frame=3`;
- `command=16`;
- `autocontinue=1`;
- параметры `p1...p4` берутся из `point.params`, если они были переданы, иначе `0`.

##### 2. Старт миссии

Action:

- `drone.mission.start`

Сообщение:

```json
{
  "action": "drone.mission.start",
  "sender": "gcs_drone_manager",
  "correlation_id": "corr-start-001",
  "payload": {}
}
```

#### Телеметрия, которую GCS принимает от дрона или симулятора

Топик:

- `v1.gcs.1.drone_manager`

Action:

- `telemetry.save`

Минимальное сообщение:

```json
{
  "action": "telemetry.save",
  "sender": "drone_adapter",
  "correlation_id": "corr-telemetry-001",
  "payload": {
    "telemetry": {
      "drone_id": "drone-01",
      "battery": 87,
      "latitude": 55.751244,
      "longitude": 37.618423,
      "altitude": 120
    }
  }
}
```

Что делает GCS:

- сохраняет состояние дрона в `drone_store`;
- обновляет `battery`, если поле присутствует;
- обновляет `last_position`, если пришли `latitude` и `longitude`;
- если дрон ранее не был зарегистрирован, создает запись и выставляет базовый статус `connected`.

Синхронный ответ не предусмотрен.

### Хранимые сущности и статусы

#### Миссия

Миссия хранится в Redis и содержит как минимум:

```json
{
  "mission_id": "m-abcdef123456",
  "waypoints": [],
  "status": "created",
  "assigned_drone": null,
  "created_at": "2026-03-17T10:00:00+00:00",
  "updated_at": "2026-03-17T10:00:00+00:00"
}
```

Статусы миссии:

- `created`
- `assigned`
- `running`

#### Дрон

Состояние дрона хранится в Redis и может содержать:

```json
{
  "status": "reserved",
  "battery": 87,
  "connected_at": "2026-03-17T10:00:00+00:00",
  "last_position": {
    "latitude": 55.751244,
    "longitude": 37.618423,
    "altitude": 120
  }
}
```

Статусы дрона, используемые GCS:

- `connected` - создан по первой телеметрии;
- `available` - предусмотрен моделью и индексом хранилища;
- `reserved` - миссия назначена, но еще не стартовала;
- `busy` - миссия запущена.

## Запуск

### Веб-интерфейс НУС

Для интерактивной демонстрации используется web UI:

- `demo/web_demo.py`

Он использует `demo/interactive_demo.py` и умеет:

- собрать `.generated/docker-compose.yml` для `systems/gcs`;
- поднять broker и GCS перед публикацией UI;
- подключить web-клиент к реальному `SystemBus`;
- интерактивно отправлять команды НУС и смотреть ответы, логи и снимок состояния.

### Требования

- Docker + Docker Compose
- Python `>= 3.12`
- `pipenv`

### 1. Подготовить окружение

```bash
cp docker/example.env docker/.env
make init
```

По умолчанию в [docker/example.env](/home/kaitrye/DronePortGCS/docker/example.env) стоит:

- `BROKER_TYPE=mqtt`
- `INSTANCE_ID=1`

### 2. Поднять брокерную инфраструктуру

```bash
make docker-up
```

### 3. Поднять GCS

```bash
make gcs-system-up
```

Команда:

- соберет `systems/gcs/.generated/docker-compose.yml`;
- сгенерирует `systems/gcs/.generated/.env`;
- поднимет `redis`, `mission_store`, `drone_store`, `mission_converter`, `orchestrator`, `path_planner`, `drone_manager` вместе с MQTT-брокером.

### 4. Поднять DronePort

```bash
make drone-port-system-up
```

Команда:

- соберет `systems/drone_port/.generated/docker-compose.yml`;
- сгенерирует `systems/drone_port/.generated/.env`;
- поднимет `redis`, `state_store`, `port_manager`, `drone_registry`, `charging_manager`, `drone_manager`, `orchestrator`.

### 5. Поднять SITL (общий MQTT с НУС и Дронопортом)

Файл [docker/docker-compose.sitl.yml](docker/docker-compose.sitl.yml) подключает сервисы из каталога `SITL-module-main/SITL-module-main` (относительно корня репозитория Integ): verifier, controller, core, messaging и Redis `sitl_redis`. Событие взлёта с Дронопорта уходит в SITL напрямую: компонент `drone_manager` публикует HOME на топик `SITL_HOME_TOPIC` (по умолчанию `sitl-drone-home`), в том же виде, что ожидает verifier и загрузка миссии в Агродроне.

Требуется уже поднятый брокер (`make docker-up` с профилем `mqtt`).

```bash
make sitl-up
```

Полный стек (брокер + GCS + DronePort + SITL):

```bash
make stack-with-sitl-up
```

Остановка SITL: `make sitl-down` или `make stack-with-sitl-down` (останавливает всё в обратном порядке).

**Веб-интерфейс НУС** этими командами **не запускается** — поднимаются только контейнеры. Чтобы открыть UI после уже запущенного стека (`make stack-with-sitl-up` или отдельно `docker-up` + `gcs-system-up` + …), в другом терминале из корня репозитория:

```bash
make init   # один раз, если нет pipenv/зависимостей
export GCS_WEB_AUTO_BOOTSTRAP=0
PYTHONPATH=. pipenv run python demo/web_demo.py
```

`GCS_WEB_AUTO_BOOTSTRAP=0` отключает повторный запуск Docker из демо (брокер и GCS уже работают). Адрес по умолчанию: `http://localhost:8000` (порт задаётся `GCS_WEB_PORT`).

### 6. Остановить сервисы

```bash
make gcs-system-down
make drone-port-system-down
make docker-down
```

Если нужен только prepare без запуска, используйте:

```bash
make -C systems/gcs prepare
make -C systems/drone_port prepare
```

### Основные переменные окружения

| Переменная | Значение по умолчанию | Назначение |
|------------|------------------------|------------|
| `BROKER_TYPE` | `mqtt` | Тип брокера. Сейчас поддерживается только `mqtt` |
| `INSTANCE_ID` | `1` | Идентификатор экземпляра GCS |
| `TOPIC_VERSION` | `v1` | Версия префикса топиков |
| `GCS_SYSTEM_NAME` | `gcs` | Имя системы в адресации |
| `MQTT_BROKER` | `mosquitto` / `localhost` | MQTT broker host |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:29092` | Зарезервировано под Kafka, в текущей реализации не используется |
| `BROKER_USER` | из `ADMIN_USER` | Логин брокера |
| `BROKER_PASSWORD` | из `ADMIN_PASSWORD` | Пароль брокера |
| `MISSION_STORE_REDIS_DB` | `0` | Redis DB для миссий |
| `DRONE_STORE_REDIS_DB` | `1` | Redis DB для дронов |

## Тесты

Все тесты:

```bash
make tests
```

Только unit:

```bash
make unit-test
```

Только интеграционные:

```bash
make integration-test
```
