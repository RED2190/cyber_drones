# Системы

Шаблон: `systems/dummy_system/`

## Внешние репозитории (git submodule)

Часть систем живёт в **отдельных репозиториях** и подключена как `git submodule` напрямую в `systems/`.

| Путь | Удалённый репозиторий | Ветка |
|---|---|---|
| `systems/orvd_system` | [autoryuzo/OpBD](https://github.com/autoryuzo/OpBD.git) | `system` |
| `systems/insurer` | [DashDashh/Insurer](https://github.com/DashDashh/Insurer.git) | `integration` |
| `systems/agrodron` | [itmoniks/cyber_drons](https://gitflic.ru/project/itmoniks/cyber_drons.git) | `agrodron_for_andrey` |
| `systems/drones` | [AMCP-Drones/drones](https://github.com/AMCP-Drones/drones.git) | `extract/only-system` |
| `systems/DroneAnalytics` | [OurPaintTeam/DroneAnalytics](https://github.com/OurPaintTeam/DroneAnalytics.git) | `main` |

**Симлинк** (для совместимости путей в docker-compose):

| Симлинк | Цель |
|---|---|
| `systems/deliverydron` | `drones` |

### Правило: всегда работай через `systems/`

Скрипты, docker-compose, `prepare_multi.py`, E2E-тесты — **всё** ходит через `systems/<имя>`.

### Клон с сабмодулями

```bash
git clone --recurse-submodules <url-этого-репозитория>
# или после обычного clone:
git submodule update --init --recursive
```

### Обновить сабмодули до зафиксированных SHA

```bash
git submodule update --init --recursive
```

### Подтянуть новые коммиты из апстрима

```bash
git submodule update --remote --recursive
# затем при необходимости закоммить обновлённые SHA
```

Остальные системы (`agregator`, `gcs`, `operator`, `regulator`, `dummy_system`, …) живут прямо в этом репозитории.

## Создать свою систему

1. Скопировать `dummy_system` → `systems/my_system/`
2. В `src/` — полные копии компонентов: `my_system/src/my_component_a/`, `my_system/src/my_component_b/`
3. Каждый компонент: `src/`, `topics.py`, `.env`, `__main__.py`, `docker/Dockerfile`
4. `docker-compose.yml` — только сервисы компонентов (без брокера)
5. `make prepare` — собирает .generated/ (брокер + компоненты)
6. `make docker-up` — запуск

## Структура

```
systems/my_system/
├── src/
│   ├── my_component_a/
│   │   ├── src/
│   │   ├── topics.py
│   │   ├── .env            # COMPONENT_ID, BROKER_USER, BROKER_PASSWORD
│   │   ├── __main__.py
│   │   └── docker/Dockerfile
│   └── my_component_b/
├── docker-compose.yml
├── .generated/
├── tests/
└── Makefile
```

## Команды

```bash
cd systems/my_system
make prepare
make docker-up
make unit-test
make integration-test
```

## .env компонента

`COMPONENT_ID`, `BROKER_USER`, `BROKER_PASSWORD`, `HEALTH_PORT`. Без `BROKER_TYPE`, портов брокера, админских кредов.
