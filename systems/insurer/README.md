# Insurer
Сервис страховой компании для обработки инцидентов и рассчёта полисов.

## Стек
- Java 17
- Apache Kafka
- Mosquitto
- Docker
- H2 db (inmemory база данных, позже переведём на PostgreSQL)

## Запуск
```bash
# Локальная разработка (dev compose)
make docker-up COMPOSE_FILE=docker-compose.dev.yml
make wait-kafka COMPOSE_FILE=docker-compose.dev.yml

# Логи
make docker-logs COMPOSE_FILE=docker-compose.dev.yml

# Остановка
make docker-down COMPOSE_FILE=docker-compose.dev.yml

# Продовый compose (требует внешнюю инфраструктуру)
make docker-up

# Запуск с нужным количеством реплик insurance-service
make docker-up INSURANCE_REPLICAS=<Количество реплик сервиса>
```

## Тесты
```bash
# Интеграционные тесты (используется отдельный test/dev compose)
make integration-test

# Все тесты
make tests
```

## Переменные окружения
Для локального запуска через `docker-compose.dev.yml` базовые переменные Kafka уже заданы в compose-файле.

Файл `.env` используется для дополнительных локальных переопределений (например, namespace и других параметров приложения),
но для CI и интеграционных тестов он не обязателен.


## Форматы сообщений для брокера

### Топики
- Слушаем: ```systems.insurance_system```
- Отвечаем в ```reply_to```, если указан. Иначе в ```systems.<sender_from_request>```

### Запросы
Request, хранящийся в payload, для любого запроса имеет одинаковую структуру. Поля, не относящиеся к типу запроса остаются null. Тип запроса указывается в поле request_type.

### ПРИМЕРЫ:

### annual_insurance:
#### Запрос:
```json
{
  "message_id": "msg-001-2026",
  "action": "annual_insurance",
  "sender": "operator",
  "reply_to": "systems.operator",
  "correlation_id": "corr-123-2026",
  "timestamp": 1743552000000,
  "payload": {
    "request_id": "req-20260319-001",
    "order_id": "order-12345",
    "manufacturer_id": "manuf-001",
    "operator_id": "oper-001",
    "drone_id": "drone-789",
    "security_goals": [
      "ЦБ1",
      "ЦБ2"
    ],
    "coverage_amount": 150000,
    "calculation_id": "calc-678-2026",
    "incident": null,
    "request_type": "CALCULATION"
  },
  "message_type": "request",
  "headers": {
    "version": "1.0",
    "source": "insurance-api"
  }
}
```
#### Ответ:
```json
{
   "message_id": "e16782d5-a2ad-4e3c-8bd0-f7be716b4d00",
   "correlation_id": "corr-123-2026",
   "timestamp": 1776001471125,
   "payload": {
      "coverage_amount": 150000,
      "drone_id": "drone-789",
      "end_date": "2027-04-12T13:44:31.029306819",
      "kfleet_history": 1,
      "manufacturer_kbm": null,
      "message": "Полис успешно оформлен",
      "new_manufacturer_kbm": null,
      "new_operator_kbm": null,
      "operator_kbm": null,
      "order_id": "order-12345",
      "payment_amount": null,
      "policy_id": "4d18e981-e68c-43ec-9b02-b62245897401",
      "policy_type": "annual",
      "premium": 12000,
      "request_id": "req-20260319-001",
      "response_id": "eeb81977-2bbe-4bc2-9626-e0601cb7b197",
      "start_date": "2026-04-12T13:44:31.029275288",
      "status": "active"
   },
   "message_type": "response",
   "success": true
}
```

### mission_insurance:
#### Запрос:
```json
{
  "message_id": "msg-001-2026",
  "action": "mission_insurance",
  "sender": "operator",
  "reply_to": "systems.operator",
  "correlation_id": "corr-123-2026",
  "timestamp": 1743552000000,
  "payload": {
    "request_id": "req-20260319-001",
    "order_id": "order-12345",
    "manufacturer_id": "manuf-001",
    "operator_id": "oper-001",
    "drone_id": "drone-789",
    "security_goals": [
      "ЦБ1",
      "ЦБ2"
    ],
    "coverage_amount": 150000,
    "calculation_id": "calc-678-2026",
    "incident": null,
    "request_type": "CALCULATION"
  },
  "message_type": "request",
  "headers": {
    "version": "1.0",
    "source": "insurance-api"
  }
}
```
#### Ответ:
```json
{
   "message_id": "7fef6715-4f48-4e10-b713-e98c51074cc4",
   "correlation_id": "corr-123-2026",
   "timestamp": 1776001789436,
   "payload": {
      "coverage_amount": 150000,
      "drone_id": "drone-789",
      "end_date": "2027-04-12T13:49:49.424257351",
      "kfleet_history": 1,
      "manufacturer_kbm": null,
      "message": "Полис успешно оформлен",
      "new_manufacturer_kbm": null,
      "new_operator_kbm": null,
      "operator_kbm": null,
      "order_id": "order-12345",
      "payment_amount": null,
      "policy_id": "8cb4235b-085c-48f8-958d-7a91879f9da3",
      "policy_type": "mission",
      "premium": 12000,
      "request_id": "req-20260319-001",
      "response_id": "6eb454e8-944d-4ffe-b2ef-013f103136dc",
      "start_date": "2026-04-12T13:49:49.424252212",
      "status": "active"
   },
   "message_type": "response",
   "success": true
}
```

### Проверка стоимости.

#### Запрос:
```json
{
  "message_id": "msg-001-2026",
  "action": "CALCULATION",
  "sender": "operator",
  "correlation_id": "corr-123-2026",
  "timestamp": 1743552000000,
  "payload": {
    "request_id": "req-20260319-001",
    "order_id": "order-12345",
    "manufacturer_id": "manuf-001",
    "operator_id": "oper-001",
    "drone_id": "drone-789",
    "security_goals": [
      "ЦБ1",
      "ЦБ2"
    ],
    "coverage_amount": 5000000.00,
    "calculation_id": "calc-678-2026",
    "incident": null,
    "request_type": "CALCULATION"
  },
  "message_type": "request",
  "headers": {
    "version": "1.0",
    "source": "insurance-api"
  }
}
```
#### Ответ:
```json
{
  "message_id": "f0703581-3b0a-4218-91bc-3b4b9c1a223f",
  "correlation_id": "req-20260319-001",
  "timestamp": 1775243455910,
  "payload": {
    "calculated_cost": 1000,
    "coverage_amount": 5000000,
    "manufacturer_kbm": 1,
    "message": "Расчёт выполнен успешно",
    "new_manufacturer_kbm": null,
    "new_operator_kbm": null,
    "operator_kbm": 1,
    "order_id": "order-12345",
    "payment_amount": null,
    "policy_end_date": null,
    "policy_id": null,
    "policy_start_date": null,
    "request_id": "req-20260319-001",
    "response_id": "349f1af7-d6b8-4ca4-8e75-4cb5ffc22be8",
    "status": "SUCCESS"
  },
  "message_type": "response"
}
```

### Покупка полиса.
#### Запрос:
```json
{
  "message_id": "msg-002-2026",
  "action": "PURCHASE",
  "sender": "operator",
  "correlation_id": "corr-124-2026",
  "timestamp": 1743552000000,
  "payload": {
    "request_id": "req-20260319-001",
    "order_id": "order-12345",
    "manufacturer_id": "manuf-001",
    "operator_id": "oper-001",
    "drone_id": "drone-789",
    "security_goals": [
      "ЦБ1",
      "ЦБ2"
    ],
    "coverage_amount": 5000000.00,
    "calculation_id": "calc-678-2026",
    "incident": null,
    "request_type": "PURCHASE"
  },
  "message_type": "request",
  "headers": {
    "version": "1.0",
    "source": "insurance-api"
  }
}
```
#### Ответ:
```json
{
  "message_id": "ac0a0ef0-8b28-48cc-96a1-a71034f585e4",
  "correlation_id": "req-20260319-001",
  "timestamp": 1775243532529,
  "payload": {
    "calculated_cost": 1000,
    "coverage_amount": 5000000,
    "manufacturer_kbm": null,
    "message": "Полис успешно оформлен",
    "new_manufacturer_kbm": null,
    "new_operator_kbm": null,
    "operator_kbm": null,
    "order_id": "order-12345",
    "payment_amount": null,
    "policy_end_date": "2026-05-03T19:12:12.421197944",
    "policy_id": "39d41898-459b-4c87-9e53-e6a371ea09bc",
    "policy_start_date": "2026-04-03T19:12:12.421171173",
    "request_id": "req-20260319-001",
    "response_id": "23f00e8f-3452-4878-8eea-630440fbc3c9",
    "status": "SUCCESS"
  },
  "message_type": "response"
}
```

### Обработка инцидента.
#### Запрос:
```json
{
  "message_id": "msg-003-2026",
  "action": "INCIDENT",
  "sender": "operator",
  "correlation_id": "corr-125-2026",
  "timestamp": 1743552000000,
  "payload": {
    "request_id": "req-20260320-001",
    "order_id": "order-12345",
    "manufacturer_id": "manuf-001",
    "operator_id": "oper-001",
    "drone_id": "drone-789",
    "security_goals": ["ЦБ1", "ЦБ2"],
    "coverage_amount": 5000000.00,
    "calculation_id": null,
    "incident": {
      "id": null,
      "incident_id": "inc-20260320-001",
      "order_id": "order-12345",
      "policy_id": "401479e6-9021-477f-83f9-50efd1e64da3",
      "damage_amount": 150000.00,
      "incident_date": "2026-03-20T14:30:00",
      "status": "REPORTED"
    },
    "request_type": "INCIDENT"
  },
  "message_type": "request",
  "headers": {
    "version": "1.0",
    "source": "insurance-api"
  }
}
```
#### Ответ:
```json
{
  "message_id": "f41b91dc-b5ba-44c9-8fc2-ee083f5ea38c",
  "correlation_id": "req-20260320-001",
  "timestamp": 1775243567393,
  "payload": {
    "calculated_cost": null,
    "coverage_amount": 150000,
    "manufacturer_kbm": null,
    "message": "Инцидент обработан, произведена выплата",
    "new_manufacturer_kbm": 1.1,
    "new_operator_kbm": 1.1,
    "operator_kbm": null,
    "order_id": "order-12345",
    "payment_amount": 150000,
    "policy_end_date": null,
    "policy_id": null,
    "policy_start_date": null,
    "request_id": "req-20260320-001",
    "response_id": "2a40fb05-42e9-4445-9279-4f64574dba57",
    "status": "SUCCESS"
  },
  "message_type": "response"
}
```

### Прекращение полиса.
#### Запрос:
```json
{
  "message_id": "msg-004-2026",
  "action": "INSURANCE_REQUEST",
  "sender": "operator",
  "correlation_id": "corr-126-2026",
  "timestamp": 1743552000000,
  "payload": {
    "request_id": "req-20260320-003",
    "order_id": "order-12345",
    "manufacturer_id": "manuf-001",
    "operator_id": "oper-001",
    "drone_id": "drone-789",
    "security_goals": ["ЦБ1", "ЦБ2"],
    "coverage_amount": 5000000.00,
    "calculation_id": null,
    "incident": null,
    "request_type": "POLICY_TERMINATION"
  },
  "message_type": "request",
  "headers": {
    "version": "1.0",
    "source": "insurance-api",
    "reason": "operator_request"
  }
}
```
#### Ответ:
```json
{
  "message_id": "128ec071-a419-42d7-b03c-cc1c384ed0c2",
  "correlation_id": "req-20260320-003",
  "timestamp": 1775243592393,
  "payload": {
    "calculated_cost": null,
    "coverage_amount": null,
    "manufacturer_kbm": null,
    "message": "Полис успешно прекращён",
    "new_manufacturer_kbm": null,
    "new_operator_kbm": null,
    "operator_kbm": null,
    "order_id": "order-12345",
    "payment_amount": null,
    "policy_end_date": null,
    "policy_id": null,
    "policy_start_date": null,
    "request_id": "req-20260320-003",
    "response_id": "9c7504eb-0c4d-4abc-8055-57eccbd8e3cb",
    "status": "SUCCESS"
  },
  "message_type": "response"
}
```
