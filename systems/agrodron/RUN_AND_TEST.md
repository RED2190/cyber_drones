# Запуск системы AgroDron и запуск тестов

## Требования

- **Python 3.12**
- **pipenv** (установка: `pip install pipenv`)
- **Docker** и **Docker Compose** (для запуска системы в контейнерах и для интеграционных тестов)
- На **Windows**: для команд `make` нужен WSL или Git Bash (либо выполняйте эквивалентные команды вручную из раздела ниже)

Зависимости проекта задаются в `config/Pipfile`. Из корня репозитория:

```bash
cd config
pipenv install
pipenv install --dev
cd ..
```

---

## 1. Поднять систему (Docker)

В монорепозитории `cyber_drons` код системы лежит в `systems/agrodron/`. У каждого компонента — `.env` в `systems/agrodron/src/<component>/.env`. Генератор собирает из них общий `systems/agrodron/.generated/.env` и единый `docker-compose`.

### 1.1. Выбор брокера

В `docker/.env` у корня монорепозитория (или в окружении) задайте брокер:

- **Kafka**: `BROKER_TYPE=kafka`
- **MQTT**: `BROKER_TYPE=mqtt`

Если не задано, по умолчанию используется `kafka`.

### 1.2. Запуск из каталога `systems/agrodron`

```bash
cd systems/agrodron
make docker-up
```

Эта команда:

1. Выполняет **prepare** из корня монорепозитория: `python systems/agrodron/scripts/prepare_system.py systems/agrodron` (см. `Makefile`), читает `.env` компонентов в `systems/agrodron/src/`, собирает `systems/agrodron/.generated/docker-compose.yml` и `.env`.
2. Поднимает брокер (Kafka или Mosquitto) и все сервисы системы с профилем `kafka` или `mqtt`.

Эквивалент вручную (без make):

```bash
# из корня монорепозитория (рядом с docker/, config/, scripts/)
cd config
pipenv run python ../systems/agrodron/scripts/prepare_system.py systems/agrodron
cd ../systems/agrodron
# подставить kafka или mqtt
docker compose -f .generated/docker-compose.yml --env-file .generated/.env --profile mqtt up -d --build
```

### 1.3. Проверка, что всё запущено

```bash
docker ps
```

Должны быть контейнеры: брокер (kafka или mosquitto), security_monitor, journal, navigation, autopilot, limiter, emergensy, mission_handler, motors, sprayer, telemetry.

### 1.4. Логи

**Все контейнеры разом:**

```bash
cd systems/agrodron
make docker-logs
```

**Логи при интеграционных тестах (proxy_request, отладка):**

Логирование уже включено в коде (security_monitor, BaseComponent). Логи пишутся в stdout контейнеров. Чтобы их видеть:

1. Поднимите систему и **не останавливайте** контейнеры:
   ```bash
   cd systems/agrodron
   make docker-up
   # подождите ~45 с
   ```

2. В **другом терминале** включите просмотр логов нужного сервиса:
   ```bash
   cd systems/agrodron
   make docker-logs-sm      # только security_monitor (входящие proxy_request, ответы/таймауты)
   # или
   make docker-logs-motors  # только motors (входящие запросы, отправка ответа)
   ```

3. В **первом терминале** запустите интеграционные тесты:
   ```bash
   cd systems/agrodron
   set -a && . .generated/.env && set +a
   export MQTT_BROKER=localhost MQTT_PORT=1883 BROKER_TYPE=mqtt BROKER_USER=admin BROKER_PASSWORD=admin_secret_123
   pipenv run pytest -c ../config/pyproject.toml tests/test_full_system_run.py tests/test_integration.py -v -s
   ```

   В окне с `make docker-logs-sm` появятся строки вида:
   - `[security_monitor] proxy_request: sender=telemetry -> agrodron.motors action=get_state`
   - `[security_monitor] proxy_request -> bus.request(agrodron.motors, timeout=10.0s)`
   - либо `proxy_request: no response from agrodron.motors (timeout or error)`, либо `got response from agrodron.motors, replying to client`.

**После прогона (контейнеры ещё запущены):**

```bash
# последние 200 строк security_monitor
docker compose -f .generated/docker-compose.yml --env-file .generated/.env --profile mqtt logs --tail=200 security_monitor

# последние 100 строк motors
docker compose -f .generated/docker-compose.yml --env-file .generated/.env --profile mqtt logs --tail=100 motors
```

Или через make (из каталога agrodron):

```bash
docker compose -f .generated/docker-compose.yml --env-file .generated/.env --profile mqtt logs --tail=200 security_monitor
```

**Как по логам понять, почему падают тесты**

Смотрите логи security_monitor (`make docker-logs-sm`). Что искать:

| В логах | Что это значит | Что делать |
|--------|--------------------------------|------------|
| **`proxy_request denied by policy: sender=... topic=... action=...`** | Монитор отклонил запрос: в политиках нет правила для этой пары (sender, topic, action) или политики в контейнер не попали / подставились с ошибкой. | Проверить, что в `.generated/.env` есть `SECURITY_MONITOR_SECURITY_POLICIES` и что в нём подставлен `SYSTEM_NAME` (должно быть `agrodron.navigation`, а не `.navigation`). Перегенерировать: `make prepare`, затем заново `make docker-up`. |
| **`proxy_request -> bus.request(agrodron.motors, timeout=10.0s)`** и дальше **`no response from agrodron.motors (timeout or error)`** | Политика разрешила запрос, но целевой компонент (motors) не ответил за 10 с. | Смотреть логи целевого контейнера (`make docker-logs-motors`): приходит ли запрос (`request action=get_state reply_to=...`), уходит ли ответ (`response sent to ...`). Если запрос не приходит — топики/сеть; если не уходит ответ — ошибка в компоненте или в reply_to. |
| **`got response from agrodron.motors, replying to client`** | Монитор получил ответ от motors и отправил его тесту. | Если тест всё равно падает по таймауту — возможна потеря ответа до теста (топик reply, сеть). Проверить топики и что тест подписан на свой `replies/...`. |
| Первый запрос к МБ проходит, дальше таймауты / у **system_monitor** «ответ не dict» при неизменном старом снимке | Очередь на обработку входящих MQTT-сообщений: мало потоков в пуле, все заняты блокирующими `proxy_request`. | Увеличить **`MQTT_BUS_CALLBACK_WORKERS`** (по умолчанию 32, см. `docs/SYSTEM.md`). При необходимости поднять **`SYSTEM_MONITOR_TELEMETRY_TIMEOUT_S`**. |

Кратко: **`denied by policy`** → чинить политики (и подстановку SYSTEM_NAME); **`no response from X`** → чинить целевой компонент или доставку ответа до монитора; **просадки под нагрузкой на MQTT** → смотреть **`MQTT_BUS_CALLBACK_WORKERS`**.

**Важно:** после изменения `.generated/.env` (например после `make prepare` или правок политик) контейнеры продолжают работать со **старым** окружением. Чтобы применить новый `.env`, нужно перезапустить стек:

```bash
cd systems/agrodron
make docker-down
make docker-up
# подождать ~45 с, затем запускать тесты или смотреть логи
```

### 1.5. Остановка

```bash
cd systems/agrodron
make docker-down
```

При необходимости выполнить для обоих профилей:

```bash
docker compose -f .generated/docker-compose.yml --env-file .generated/.env --profile kafka down
docker compose -f .generated/docker-compose.yml --env-file .generated/.env --profile mqtt down
```

---

## 2. Тесты

Запуск из каталога **agrodron** (путь к Pipfile и pytest задаётся относительно него).

### 2.1. Проверка окружения для тестов

```bash
cd systems/agrodron
make check-tools
```

Убедитесь, что доступны `pipenv` и `pytest` (через `config/Pipfile`).

### 2.2. Unit-тесты (без Docker)

Тесты компонентов лежат в `systems/agrodron/src/*/tests/`.

```bash
cd systems/agrodron
make unit-test
```

Эквивалент вручную:

```bash
cd systems/agrodron
PIPENV_PIPFILE=../config/Pipfile pipenv run pytest -c ../config/pyproject.toml components -vv -rA -s
```

Будут выполнены, в том числе:

- `components/autopilot/tests/`
- `components/emergensy/tests/`
- `components/journal/tests/`
- `components/limiter/tests/`
- `components/mission_handler/tests/`
- `components/navigation/tests/`

### 2.3. Интеграционные тесты (с Docker)

Сначала поднимается вся система, затем запускается один интеграционный тест-файл:

```bash
cd systems/agrodron
make integration-test
```

Это по сути:

1. `make docker-up`
2. Ожидание ~45 с
3. Запуск: `pytest -c ../config/pyproject.toml tests/test_integration.py -vv -rA -s`
4. `make docker-down`

Если нужных интеграционных тестов ещё нет, эта цель может падать. В таком случае ограничьтесь unit-тестами: `make unit-test`.

### 2.4. Все тесты (unit + integration)

```bash
cd systems/agrodron
make tests
```

Сначала выполняются unit-тесты, затем интеграционные (при наличии `tests/test_integration.py` и Docker).

---

## 3. Полный прогон системы (как реальный запуск дрона)

Одна команда поднимает систему и прогоняет **все тесты подряд с краткими описаниями**: unit-тесты компонентов, затем сценарии ОРВД/НСУ, наземная станция, SITL, автопилот, приводы, опрыскиватель, навигация, телеметрия, ограничитель, экстренные ситуации, журнал, МБ.

**Из каталога `agrodron`:**

```bash
make full-run
```

Это по сути: `make docker-up` → ожидание 45 с → **make run-all** → `make docker-down`.

**Только прогон тестов** (система уже поднята, например после `make docker-up`):

```bash
cd systems/agrodron
set -a && . .generated/.env && set +a
make run-all
```

Перед каждым тестом выводится краткое описание (первая строка docstring). Сценарии полного прогона лежат в `tests/test_full_system_run.py` (нумерация 01–17).

---

## 4. Краткая шпаргалка


| Действие                                             | Команда (из каталога `agrodron`) |
| ---------------------------------------------------- | -------------------------------- |
| **Полный прогон (поднять + тесты + остановить)**     | `make full-run`                  |
| Все тесты подряд с описаниями (unit + полный прогон) | `make run-all`                   |
| Собрать .generated и поднять систему                 | `make docker-up`                 |
| Остановить систему                                   | `make docker-down`               |
| Логи контейнеров                                     | `make docker-logs`               |
| Только пересобрать .generated                        | `make prepare`                   |
| Unit-тесты                                           | `make unit-test`                 |
| Интеграционные тесты (Docker)                        | `make integration-test`          |
| Всё: unit + integration                              | `make tests`                     |
| Справка по целям                                     | `make help`                      |


---

## 5. Переменные окружения при запуске

- **BROKER_TYPE** — `kafka` или `mqtt` (учитывается при `make docker-up` и `make docker-logs`).
- Конфигурация компонентов берётся из их `.env` в `systems/agrodron/src/<component>/.env` при каждом `make prepare`; итог попадает в `systems/agrodron/.generated/.env`.

Если вы меняли только `.env` компонентов, достаточно снова выполнить:

```bash
make prepare
make docker-up
```

