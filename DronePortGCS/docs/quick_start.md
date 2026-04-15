# Quick Start

Быстрый старт по репозиторию `DronePortGCS`: общая инфраструктура, `GCS`, `DronePort`, тесты и основные команды.

## Что в репозитории

- `broker/` - шина сообщений и фабрика брокеров
- `sdk/` - базовые классы, протокол сообщений, общие утилиты
- `components/` - standalone-компоненты
- `systems/gcs/` - наземная станция управления миссиями
- `systems/drone_port/` - сервис дронопорта
- `docker/` - общая брокерная инфраструктура
- `docs/` - общая документация

## Требования

- Docker + Docker Compose
- Python `>= 3.12`
- `pipenv`
- `git submodule` support

## Быстрый сценарий

```bash
git submodule update --init --recursive
cp docker/example.env docker/.env
make init
make docker-up
make gcs-system-up
make drone-port-system-up
```

Остановить всё:

```bash
make gcs-system-down
make drone-port-system-down
make docker-down
```

## Веб-демо вместо ноутбука

Для demo-команд НУС можно поднять web UI. При старте он сам поднимет `broker + GCS + DronePort + AgroDron`, дождется готовности компонентов и только потом откроет web-интерфейс:

```bash
PYTHONPATH=. python3 demo/web_demo.py
```

После успешного автоподъема откройте:

```text
http://localhost:8000
```

Для доступа с других устройств в той же сети можно запустить явно на всех интерфейсах:

```bash
GCS_WEB_HOST=0.0.0.0 GCS_WEB_PORT=8000 PYTHONPATH=. python3 demo/web_demo.py
```

Тогда открывайте интерфейс с другого устройства по IP машины, на которой запущен сервер, например:

```text
http://192.168.1.50:8000
```

Если интерфейс не открывается с другого устройства, обычно не хватает:

- открытого порта `8000` в локальном firewall;
- доступа между устройствами в одной сети;
- правильного IP адреса хоста.

Через страницу можно:

- поднять или остановить `broker` и `GCS`;
- создать, назначить и запустить миссию;
- посмотреть `snapshot`, `ps` и docker-логи.

Если нужен запуск без автоподъема контейнеров:

```bash
GCS_WEB_AUTO_BOOTSTRAP=0 PYTHONPATH=. python3 demo/web_demo.py
```

## Основные команды

```bash
make help
make init
make unit-test
make integration-test
make integration-test-run
make tests
```

```bash
make docker-up
make docker-down
make docker-logs
make docker-ps
make docker-clean
```

```bash
make gcs-system-up
make gcs-system-down
make drone-port-system-up
make drone-port-system-down
```

## Что делают system-up команды

`make gcs-system-up`:

- запускает `make -C systems/gcs prepare`
- генерирует `systems/gcs/.generated/docker-compose.yml`
- генерирует `systems/gcs/.generated/.env`
- поднимает `redis`, `mission_store`, `drone_store`, `mission_converter`, `orchestrator`, `path_planner`, `drone_manager`

`make drone-port-system-up`:

- запускает `make -C systems/drone_port prepare`
- генерирует `systems/drone_port/.generated/docker-compose.yml`
- генерирует `systems/drone_port/.generated/.env`
- поднимает `redis`, `state_store`, `port_manager`, `drone_registry`, `charging_manager`, `drone_manager`, `orchestrator`

Если нужен только prepare без запуска:

```bash
make -C systems/gcs prepare
make -C systems/drone_port prepare
```

## Брокер и env

Сейчас в документации и рабочем сценарии поддерживается только `MQTT`.

Основные переменные в `docker/.env`:

| Переменная | Назначение |
|------------|------------|
| `BROKER_TYPE` | Тип брокера. Используйте `mqtt` |
| `INSTANCE_ID` | Идентификатор экземпляра системы |
| `ADMIN_USER` | Логин администратора брокера |
| `ADMIN_PASSWORD` | Пароль администратора брокера |

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

Если docker-стек уже поднят вручную и нужен только pytest:

```bash
make integration-test-run
```

## Полезные ссылки

- [README.md](/home/kaitrye/DronePortGCS/README.md)
- [Makefile](/home/kaitrye/DronePortGCS/Makefile)
- [systems/gcs/docs/c4/README.md](/home/kaitrye/DronePortGCS/systems/gcs/docs/c4/README.md)
