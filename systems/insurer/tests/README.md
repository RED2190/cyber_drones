# Интеграционные тесты страховщика

В этой папке находятся интеграционные тесты сервиса страховой компании.
Тесты проверяют Kafka-пайплайн: отправка запроса в request topic и получение ответа из response topic.

Основной файл с тестами: insurance_integration_test.go.

## Что покрыто

- CALCULATION: успешный расчет стоимости и КБМ.
- PURCHASE + POLICY_TERMINATION: создание полиса и успешное закрытие.
- INCIDENT: успешная обработка инцидента с выплатой и пересчетом КБМ.
- INCIDENT без incident payload: ошибка валидации (FAILED).
- POLICY_TERMINATION для несуществующего заказа: ошибка (FAILED).

## Быстрый запуск

Из корня репозитория:

```bash
make integration-test
```

Эта команда:
- поднимает zookeeper, kafka, kafdrop и insurance-service;
- ждет доступности Kafka;
- запускает go test внутри контейнера tests;
- после завершения останавливает окружение.

## Ручной запуск

1. Поднять окружение:

```bash
make docker-up
```

2. Запустить тесты в контейнере:

```bash
docker compose run --build --rm --entrypoint go tests test -race -v ./...
```

3. Остановить окружение:

```bash
make docker-down
```

## Переменные окружения

Тесты можно гибко настроить через env:

- KAFKA_BROKERS: список брокеров через запятую.
	Пример: kafka:29092,localhost:9092
- INSURANCE_REQUEST_TOPIC: явное имя request topic.
- INSURANCE_RESPONSE_TOPIC: явное имя response topic.
- INSURER_INSTANCE_ID: instance id для вычисления имен топиков.
- INSTANCE_ID: fallback для instance id.

Если топики не заданы явно, используются шаблоны:

- v1.Insurer.<instanceId>.insurer-service.requests
- v1.Insurer.<instanceId>.insurer-service.responses

По умолчанию instanceId = 1.

## Локальный запуск из папки tests

```bash
go test -race -v ./...
```

Пример запуска конкретного теста:

```bash
go test -race -v -run TestIncidentRequestSuccess ./...
```
