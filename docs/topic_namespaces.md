# Топики и SYSTEM_NAMESPACE

## Иерархия топиков

Все топики в проекте делятся на три уровня:

| Шаблон | Назначение | Кто слушает |
|--------|------------|-------------|
| `systems.<имя>` | Входной топик системы | Gateway |
| `components.<имя>` | Внутренний топик компонента | Компонент |
| `errors.dead_letters` | Ошибки fire-and-forget | Мониторинг |

Внешний потребитель знает только системный топик и action.
Gateway по таблице `ACTION_ROUTING` перенаправляет запрос к нужному компоненту.

```
Внешняя система                     dummy_system
─────────────                  ┌───────────────────────┐
                               │                       │
  ──── action: echo ──────────►│  Gateway              │
  systems.dummy_system         │   │                   │
                               │   ├──► component_a    │
                               │   └──► component_b    │
                               └───────────────────────┘
```

## SYSTEM_NAMESPACE

Если на одном брокере работают несколько экземпляров одной системы,
их топики совпадут. `SYSTEM_NAMESPACE` добавляет префикс **ко всем** топикам
экземпляра — и к системным, и к компонентным:

| SYSTEM_NAMESPACE | Системный топик | Компонентный топик |
|---|---|---|
| *(не задан)* | `systems.dummy_system` | `components.dummy_component_a` |
| `fleet_1` | `fleet_1.systems.dummy_system` | `fleet_1.components.dummy_component_a` |
| `fleet_2` | `fleet_2.systems.dummy_system` | `fleet_2.components.dummy_component_a` |

Два экземпляра с разными namespace полностью изолированы.

## Как задаётся в коде

Каждый компонент и gateway определяют `topics.py` с одинаковым паттерном:

```python
import os

_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class SystemTopics:
    MY_SYSTEM = f"{_P}systems.my_system"


class ComponentTopics:
    SENSOR = f"{_P}components.sensor"
    ACTUATOR = f"{_P}components.actuator"

    @classmethod
    def all(cls) -> list:
        return [cls.SENSOR, cls.ACTUATOR]


class GatewayActions:
    READ_DATA = "read_data"
    SEND_COMMAND = "send_command"
```

Ключевые правила:

- `_NS` и `_P` вычисляются один раз при импорте модуля.
- Префикс добавляется к **`SystemTopics`** и **`ComponentTopics`**.
- `GatewayActions` — это строковые имена action (передаются внутри сообщения, а не как имя топика). Префикс к ним **не** добавляется.
- `errors.dead_letters` — глобальный топик, не привязан к namespace.

## Как передаётся через Docker Compose

В `docker-compose.yml` системы переменная прокидывается всем сервисам:

```yaml
services:
  my_component:
    environment:
      - SYSTEM_NAMESPACE=${SYSTEM_NAMESPACE:-}
      # ...

  my_gateway:
    environment:
      - SYSTEM_NAMESPACE=${SYSTEM_NAMESPACE:-}
      # ...
```

Значение берётся из `.env` или задаётся при запуске.

## Запуск нескольких экземпляров

**Через `.env`:**

```bash
echo "SYSTEM_NAMESPACE=fleet_1" >> docker/.env
make docker-up
```

**Через переменную окружения:**

```bash
SYSTEM_NAMESPACE=fleet_1 make docker-up   # первый экземпляр
SYSTEM_NAMESPACE=fleet_2 make docker-up   # второй экземпляр
```

**Без namespace (по умолчанию):**

```bash
make docker-up   # топики без префикса
```

## Межсистемное взаимодействие

Для отправки запроса в другую систему достаточно знать
её системный топик и action:

```python
response = self.bus.request(
    "systems.dummy_system",        # топик целевой системы
    {
        "action": "echo",          # action из GatewayActions
        "sender": self.system_id,
        "payload": {"text": "hi"},
    },
    timeout=10.0,
)
```

Если целевая система запущена с `SYSTEM_NAMESPACE=fleet_1`,
отправитель должен обращаться к `fleet_1.systems.dummy_system`.

## Пример: dummy_system

```
topics.py (gateway)           topics.py (component_a)
────────────────────          ──────────────────────────
SystemTopics:                 ComponentTopics:
  DUMMY_SYSTEM                  DUMMY_COMPONENT_A
                                DUMMY_COMPONENT_B
ComponentTopics:
  DUMMY_COMPONENT_A           DummyComponentActions:
  DUMMY_COMPONENT_B             ECHO, INCREMENT, GET_STATE,
                                ASK_B, GET_DATA
GatewayActions:
  ECHO, INCREMENT,
  GET_STATE, GET_DATA
```

Gateway маршрутизирует:

```python
ACTION_ROUTING = {
    GatewayActions.ECHO:      ComponentTopics.DUMMY_COMPONENT_A,
    GatewayActions.INCREMENT:  ComponentTopics.DUMMY_COMPONENT_A,
    GatewayActions.GET_STATE:  ComponentTopics.DUMMY_COMPONENT_A,
    GatewayActions.GET_DATA:   ComponentTopics.DUMMY_COMPONENT_B,
}
```


## Чеклист при создании новой системы

1. Создать `topics.py` в каждом компоненте и в gateway.
2. Во всех `topics.py` использовать паттерн `_NS` / `_P`.
3. Системный топик — `f"{_P}systems.<имя>"`.
4. Компонентные топики — `f"{_P}components.<имя>"`.
5. `GatewayActions` — просто строковые константы, **без** префикса.
6. В `docker-compose.yml` прокинуть `SYSTEM_NAMESPACE=${SYSTEM_NAMESPACE:-}` во все сервисы.
7. Определить `ACTION_ROUTING` в gateway, связав action с компонентным топиком.
