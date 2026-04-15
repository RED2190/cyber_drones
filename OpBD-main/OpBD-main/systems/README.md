# Системы

Шаблон: `systems/dummy_system/`

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
