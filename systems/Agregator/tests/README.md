# Интеграционные тесты

В этой папке находятся интеграционные тесты для API агрегатора.

Тесты:
- проверяют готовность сервиса через `/health`;
- создают заказчика и заказ через HTTP API;
- подтверждают цену заказа (`/orders/{id}/confirm-price`) и проверяют смену статуса на `confirmed`;
- проверяют список заказов;
- проверяют негативные сценарии (`400` и `404`).

## Быстрый запуск (рекомендуется)

Из корня репозитория:

```bash
make integration-test
```

Команда:
- создаст (при необходимости) Docker network `drones_net`;
- поднимет `postgres`, `aggregator`, `zookeeper`, `kafka`, `kafka-init` через `docker-compose.yml + docker-compose.dev.yml`;
- запустит `tests` контейнер (`go test -race -v ./...`);
- после завершения остановит окружение и удалит volume (`docker compose down -v --remove-orphans`).

## Ручной запуск

1. Поднять стек:

```bash
docker network create drones_net || true
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile kafka --profile tests up -d --build aggregator postgres zookeeper kafka kafka-init
```

2. Запустить интеграционные тесты:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile kafka --profile tests run --rm tests
```

3. Остановить стек:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml down -v --remove-orphans
```

## Переопределение адреса API

По умолчанию тесты пытаются подключиться к:
1. `http://aggregator:8080` (внутри docker compose сети)
2. `http://localhost:8081`

Можно явно указать адрес через переменную окружения:

```bash
AGGREGATOR_BASE_URL=http://localhost:8081 go test -race -v ./...
```

(запускать из папки `tests`)
