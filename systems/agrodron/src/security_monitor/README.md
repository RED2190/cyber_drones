# Security Monitor Component

`SecurityMonitorComponent` — шлюз безопасности для проксирования запросов к целевым компонентам по policy-модели.

В архитектуре **остальные компоненты принимают запросы только от монитора** (проверка `sender`). Клиенты обращаются к монитору; монитор по политике проксирует запрос к целевому компоненту от своего имени.

По умолчанию монитор работает в режиме **deny-all**: если политика не задана, доступ запрещен.

## Quick Start

1. Скопируйте шаблон env:

```bash
cp components/security_monitor/.env.example components/security_monitor/.env
```

2. Укажите admin sender и стартовые политики в `.env`:

- `POLICY_ADMIN_SENDER=security_monitor_admin`
- `SECURITY_POLICIES=` (пусто = deny-all, формат только JSON)

3. В составе системы задайте `SYSTEM_NAME`:

- `SYSTEM_NAME=agrodron`

Тогда топик монитора будет `agrodron.security_monitor` (если не задан `COMPONENT_TOPIC`).

4. В составе системы поднимите сервисы:

```bash
cd systems/dummy_system
make prepare
make docker-up
```

5. Базовая проверка логики:

- `proxy_request` без policy -> `None` (запрещено)
- `set_policy` от `POLICY_ADMIN_SENDER` -> `updated: true`
- `proxy_request` после `set_policy` -> разрешено

## Переменные окружения

- `SYSTEM_NAME` — имя системы (например `agrodron`). В примерах может быть `components`.
- `COMPONENT_ID` — идентификатор компонента (по умолчанию `security_monitor_standalone` в standalone entrypoint).
- `COMPONENT_TOPIC` — (опционально) полный override топика монитора.
- `POLICY_ADMIN_SENDER` — sender, которому разрешено менять политики (`set/remove/clear`).
- `SECURITY_POLICIES` — стартовые политики.
- `SECURITY_MONITOR_PROXY_REQUEST_TIMEOUT_S` — таймаут реального `request` к целевому компоненту.

Для быстрого старта используйте `components/security_monitor/.env.example`
и скопируйте его в `.env`.

### Формат `SECURITY_POLICIES`

В системе используется **только JSON-список**:

```json
[
  { "sender": "autopilot", "topic": "agrodron.navigation", "action": "get_state" },
  { "sender": "autopilot", "topic": "agrodron.motors", "action": "SET_TARGET" }
]
```

## Поддерживаемые actions

- `proxy_request` — request/response прокси на целевой топик.
- `proxy_publish` — fire-and-forget publish на целевой топик.
- `set_policy` — добавить разрешение (только `POLICY_ADMIN_SENDER`).
- `remove_policy` — удалить разрешение (только `POLICY_ADMIN_SENDER`).
- `clear_policies` — очистить все разрешения (только `POLICY_ADMIN_SENDER`).
- `list_policies` — вернуть текущие политики.
- `ISOLATION_START` — включить режим изоляции (инициатор `emergensy` или admin).
- `isolation_status` — получить текущий режим (`NORMAL`/`ISOLATED`).

## Формат proxy-запроса

```json
{
  "action": "proxy_request",
  "sender": "client_a",
  "payload": {
    "target": {
      "topic": "agrodron.some_component",
      "action": "echo"
    },
    "data": {
      "message": "hello"
    }
  }
}
```

Разрешение проверяется по тройке:

`(sender, target.topic, target.action)`

## Формат policy-операций

### Добавить policy

```json
{
  "action": "set_policy",
  "sender": "security_monitor_admin",
  "payload": {
    "sender": "client_a",
    "topic": "agrodron.some_component",
    "action": "echo"
  }
}
```

### Удалить policy

```json
{
  "action": "remove_policy",
  "sender": "security_monitor_admin",
  "payload": {
    "sender": "client_a",
    "topic": "agrodron.some_component",
    "action": "echo"
  }
}
```

### Очистить все policy

```json
{
  "action": "clear_policies",
  "sender": "security_monitor_admin",
  "payload": {}
}
```

### Посмотреть policy

```json
{
  "action": "list_policies",
  "sender": "any_sender",
  "payload": {}
}
```

## Запуск

### Standalone (без брокера)

```bash
python -m systems.agrodron.src.security_monitor
```

### В составе системы (через broker)

Используйте версию в `systems/<system>/components/security_monitor` и передавайте переменные:

- `SYSTEM_NAME`
- `COMPONENT_ID`
- `POLICY_ADMIN_SENDER`
- `SECURITY_POLICIES`
- параметры подключения к broker (`BROKER_TYPE`, `MQTT_*` / `KAFKA_*`, `BROKER_USER`, `BROKER_PASSWORD`)
