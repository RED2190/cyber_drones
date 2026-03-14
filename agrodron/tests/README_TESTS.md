# Тесты AgroDron

Кратко: какие тесты есть, где лежат и как запускать.

---

## 1. Unit-тесты (компоненты по отдельности)

**Что это:** проверка логики одного компонента без реального брокера. Подменяем шину на «заглушку» (DummyBus), вызываем обработчики (`_handle_*`) и смотрим результат и вызовы `publish`/`request`.

**Где лежат:** в каждом компоненте в папке `tests/`:

- `components/autopilot/tests/` — автопилот (mission_load, cmd, get_state)
- `components/emergensy/tests/` — экстренные ситуации (limiter_event)
- `components/journal/tests/` — журнал (LOG_EVENT → файл)
- `components/limiter/tests/` — ограничитель (mission_load, nav_state, get_state)
- `components/mission_handler/tests/` — парсер WPL и загрузка миссии
- `components/navigation/tests/` — нормализатор SITL и компонент навигации
- `components/motors/tests/` — приводы (SET_TARGET, LAND, get_state, формат SITL-команды)
- `components/sprayer/tests/` — опрыскиватель (SET_SPRAY, get_state)
- `components/security_monitor/tests/` — монитор (proxy_publish, proxy_request, политики)
- `components/telemetry/tests/` — телеметрия (get_state, proxy_get_state)

**Запуск всех unit-тестов из каталога `agrodron`:**

```bash
cd agrodron
make unit-test
```

Или вручную (из корня репозитория):

```bash
PIPENV_PIPFILE=config/Pipfile pipenv run pytest -c config/pyproject.toml agrodron/components -v
```

Запуск тестов только одного компонента, например motors:

```bash
PIPENV_PIPFILE=config/Pipfile pipenv run pytest -c config/pyproject.toml agrodron/components/motors/tests -v
```

---

## 2. Интеграционные тесты (брокер + компоненты)

**Что это:** проверка связки «клиент → брокер → монитор безопасности → компонент». Нужен запущенный брокер (и желательно контейнеры с компонентами), в окружении заданы `BROKER_TYPE` и хост/порт брокера.

**Где лежат:** `agrodron/tests/`

- `test_integration.py` — подключение к брокеру, proxy_request к МБ, get_state к motors
- `conftest.py` — общие фикстуры (broker_type, security_monitor_topic и т.д.)

**Когда выполняются:** тесты помечены `@pytest.mark.integration` и при отсутствии переменных брокера автоматически пропускаются (`skip`).

**Запуск:**

1. Поднять систему: `make docker-up` (из `agrodron`).
2. Подставить в окружение переменные из `.generated/.env` (или экспортировать их).
3. Запустить интеграционные тесты:

```bash
cd agrodron
set -a && . .generated/.env && set +a
make integration-test
```

Или только интеграционные, без перезапуска контейнеров:

```bash
set -a && . agrodron/.generated/.env && set +a
PIPENV_PIPFILE=config/Pipfile pipenv run pytest -c config/pyproject.toml agrodron/tests/test_integration.py -v -m integration
```

---

## 3. Запуск «всех» тестов

Из каталога `agrodron`:

```bash
make tests
```

Это по очереди: **unit-test**, затем **integration-test** (который сам поднимает Docker, ждёт, прогоняет интеграционные тесты и останавливает контейнеры).

---

## 4. Виды проверок в unit-тестах

| Тип проверки | Пример |
|--------------|--------|
| Доверенный отправитель | Сообщение от `security_monitor_*` обрабатывается, от `unknown` — нет. |
| Валидация payload | Неверный или не тот тип payload → ответ с `ok: false` или `None`. |
| Изменение состояния | После SET_TARGET/LAND/SET_SPRAY состояние и `get_state` соответствуют ожиданию. |
| Формат данных | Например, SITL-команда содержит `drone_id`, `vx`, `vy`, `vz`, `mag_heading`. |
| Вызов шины | DummyBus записывает `publish`/`request`; проверяем топик и тело сообщения. |

---

## 5. Структура каталогов

```
agrodron/
├── components/
│   ├── autopilot/tests/    # unit
│   ├── emergensy/tests/    # unit
│   ├── journal/tests/      # unit
│   ├── limiter/tests/      # unit
│   ├── mission_handler/tests/  # unit (WPL + компонент)
│   ├── navigation/tests/    # unit (normalizer + компонент)
│   ├── motors/tests/       # unit
│   ├── sprayer/tests/      # unit
│   ├── security_monitor/tests/  # unit
│   └── telemetry/tests/    # unit
└── tests/                  # интеграционные
    ├── conftest.py
    ├── test_integration.py
    └── README_TESTS.md     # этот файл
```

Итого: **unit** — быстрые, без Docker, в `components/*/tests/`; **integration** — с брокером и опционально с контейнерами, в `agrodron/tests/`.
