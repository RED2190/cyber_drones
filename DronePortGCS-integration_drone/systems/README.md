# Системы

## Создать свою систему

1. Создать каталог `systems/my_system/`
2. В `src/` разместить компоненты системы, например `my_system/src/my_component_a/`, `my_system/src/my_component_b/`
3. Для каждого компонента задать `src/`, `topics.py`, `.env`, `__main__.py`, `docker/Dockerfile`
4. В `docker-compose.yml` описать только сервисы компонентов системы, без брокера
5. Выполнить `make prepare` для генерации `.generated/`
6. Выполнить `make docker-up` для запуска

## Структура

```text
systems/my_system/
├── src/
│   ├── my_component_a/
│   │   ├── src/
│   │   ├── topics.py
│   │   ├── .env
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

`COMPONENT_ID`, `BROKER_USER`, `BROKER_PASSWORD`, `HEALTH_PORT`.
