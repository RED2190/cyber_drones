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

Все компоненты уже имеют рабочие `.env` в `agrodron/src/<component>/.env` с топиками `agrodron.*`. Генератор собирает из них общий `.generated/.env` и единый `docker-compose`.

### 1.1. Выбор брокера

В `docker/.env` (или в окружении) задайте брокер:

- **Kafka**: `BROKER_TYPE=kafka`
- **MQTT**: `BROKER_TYPE=mqtt`

Если не задано, по умолчанию используется `kafka`.

### 1.2. Запуск из каталога `agrodron`

```bash
cd agrodron
make docker-up
```

Эта команда:

1. Выполняет **prepare** — скрипт `scripts/prepare_system.py agrodron` читает `.env` из каждого компонента в `agrodron/src/`, собирает общий `agrodron/.generated/docker-compose.yml` и `agrodron/.generated/.env`.
2. Поднимает брокер (Kafka или Mosquitto) и все сервисы системы с профилем `kafka` или `mqtt`.

Эквивалент вручную (без make):

```bash
# из корня репозитория
cd config
pipenv run python ../scripts/prepare_system.py agrodron
cd ../agrodron
# подставить kafka или mqtt
docker compose -f .generated/docker-compose.yml --env-file .generated/.env --profile mqtt up -d --build
```

### 1.3. Проверка, что всё запущено

```bash
docker ps
```

Должны быть контейнеры: брокер (kafka или mosquitto), security_monitor, journal, navigation, autopilot, limiter, emergensy, mission_handler, motors, sprayer, telemetry.

### 1.4. Логи

```bash
cd agrodron
make docker-logs
```

Или:

```bash
docker compose -f agrodron/.generated/docker-compose.yml --env-file agrodron/.generated/.env --profile mqtt logs -f
```

### 1.5. Остановка

```bash
cd agrodron
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
cd agrodron
make check-tools
```

Убедитесь, что доступны `pipenv` и `pytest` (через `config/Pipfile`).

### 2.2. Unit-тесты (без Docker)

Тесты компонентов лежат в `agrodron/src/*/tests/`.

```bash
cd agrodron
make unit-test
```

Эквивалент вручную:

```bash
cd agrodron
PIPENV_PIPFILE=../config/Pipfile pipenv run pytest -c ../config/pyproject.toml src -vv -rA -s
```

Будут выполнены, в том числе:

- `src/autopilot/tests/`
- `src/emergensy/tests/`
- `src/journal/tests/`
- `src/limiter/tests/`
- `src/mission_handler/tests/`
- `src/navigation/tests/`

### 2.3. Интеграционные тесты (с Docker)

Сначала поднимается вся система, затем запускается один интеграционный тест-файл:

```bash
cd agrodron
make integration-test
```

Это по сути:

1. `make docker-up`
2. Ожидание ~45 с
3. Запуск: `pytest -c ../config/pyproject.toml tests/test_integration.py -vv -rA -s`
4. `make docker-down`

Если файла `agrodron/tests/test_integration.py` ещё нет, эта цель будет падать. В таком случае ограничьтесь unit-тестами: `make unit-test`.

### 2.4. Все тесты (unit + integration)

```bash
cd agrodron
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
cd agrodron
set -a && . .generated/.env && set +a
make run-all
```

Перед каждым тестом выводится краткое описание (первая строка docstring). Сценарии полного прогона лежат в `tests/test_full_system_run.py` (нумерация 01–17).

---

## 4. Краткая шпаргалка

| Действие | Команда (из каталога `agrodron`) |
|----------|-----------------------------------|
| **Полный прогон (поднять + тесты + остановить)** | `make full-run` |
| Все тесты подряд с описаниями (unit + полный прогон) | `make run-all` |
| Собрать .generated и поднять систему | `make docker-up` |
| Остановить систему | `make docker-down` |
| Логи контейнеров | `make docker-logs` |
| Только пересобрать .generated | `make prepare` |
| Unit-тесты | `make unit-test` |
| Интеграционные тесты (Docker) | `make integration-test` |
| Всё: unit + integration | `make tests` |
| Справка по целям | `make help` |

---

## 5. Переменные окружения при запуске

- **BROKER_TYPE** — `kafka` или `mqtt` (учитывается при `make docker-up` и `make docker-logs`).
- Конфигурация компонентов берётся из их `.env` в `agrodron/src/<component>/.env` при каждом `make prepare`; итог попадает в `agrodron/.generated/.env`.

Если вы меняли только `.env` компонентов, достаточно снова выполнить:

```bash
make prepare
make docker-up
```
