# Fabric Ledger Integration

Интеграция Hyperledger Fabric в sbd-drones-economics.
Компоненты вызывают смарт-контракты через шину (`bus.request("components.ledger", ...)`).

## Архитектура

```
[Компонент] → bus.request → [Ledger Gateway] → HTTP → [Fabric Proxy (Go)] → gRPC → [Fabric Peer]
```

- **Fabric Proxy** — Go-сервис с REST API, подключается к peer через `@hyperledger/fabric-gateway`
- **Ledger Gateway** — Python-сервис на шине (Kafka/MQTT), транслирует сообщения в HTTP-вызовы к Fabric Proxy

## Требования

- Hyperledger Fabric 2.5 сеть (submodule `fabric-network/`)
- Docker + Docker Compose
- Fabric-сеть запущена до `make docker-up`

## Запуск

### 1. Инициализация submodule (если клонировали без `--recursive`)

```bash
git submodule update --init --recursive
```

### 2. Запуск Fabric-сети

```bash
cd fabric-network/network
./start.sh install

./start.sh up
```

Дождитесь, пока все peers и orderer поднимутся.

### 3. Запуск sbd с Fabric

В `docker/.env`:
```
ENABLE_FABRIC=true
```

Затем:
```bash
make docker-up
# или из системы:
cd systems/dummy_system
make docker-up
```

### 4. Проверка

```bash
# Статус контейнеров
docker ps | grep -E "fabric-proxy|ledger-gateway"

# Health check
curl -s http://localhost:3000/health

# Тестовый query
curl -s -X POST http://localhost:3000/api/query \
  -H "Content-Type: application/json" \
  -d '{"method": "DronePropertiesContract:ListDronePasses", "args": []}'
```

## Вызов контрактов из компонента

### invoke (запись)

```python
result = self.bus.request(
    "components.ledger",
    {
        "action": "invoke",
        "sender": self.component_id,
        "payload": {
            "channel": "dronechannel",
            "chaincode": "drone-chaincode",
            "method": "DronePropertiesContract:CreateDronePass",
            "args": ["drone-1", "manufacturer-001", "DJI Mavic 3",
                     "agro", "25", "50", "10", "2024", "0", "fw-1"],
        },
    },
    timeout=30.0,
)
```

### query (чтение)

```python
result = self.bus.request(
    "components.ledger",
    {
        "action": "query",
        "sender": self.component_id,
        "payload": {
            "method": "DronePropertiesContract:ReadDronePass",
            "args": ["drone-1"],
        },
    },
    timeout=10.0,
)
```

### Формат ответа

```python
# Успех
{"success": True, "payload": {"result": "...", "transaction_id": "abc123"}}

# Ошибка
{"success": False, "payload": {"error": "drone not found"}}
```

## Доступные контракты

Формат вызова: `"method": "ContractName:MethodName"`. Параметры передаются в массиве `args` (порядок аргументов важен). Роли проверяются по MSP вызывающего (Aggregator, Operator, Insurer, CertCenter, Manufacturer) или по атрибуту `role=admin` в сертификате.

---

### Существующие контракты

Учёт паспортов дронов и страховых записей.

| Метод | Параметры (`args`) | Кто может вызывать |
|-------|--------------------|--------------------|
| **CreateDronePass** | `id`, `developerID`, `model`, `droneType`, `weightKg`, `maxFlightRangeKm`, `maxPayloadWeightKg`, `releaseYear`, `incidentCount`, `firmwareID` (все строки, кроме числовых: int) | CertCenter, admin |
| **ReadDronePass** | `id` | любой (чтение) |
| **UpdateDronePass** | `id`, `developerID`, `model`, `droneType`, `weightKg`, `maxFlightRangeKm`, `maxPayloadWeightKg`, `releaseYear`, `incidentCount`, `firmwareID` | CertCenter, admin |
| **DeleteDronePass** | `id` | CertCenter, admin |
| **ListDronePasses** | — | любой (чтение) |
| **CreateInsuranceRecord** | `droneID`, `insurerID`, `coverageAmount` (int) | Insurer, admin |
| **ReadInsuranceRecord** | `droneID` | любой (чтение) |
| **UpdateInsuranceStatus** | `droneID`, `status` (`active` \| `expired` \| `cancelled`) | Insurer, admin |

---

### FirmwareContract

Сертификация прошивок и привязка целей безопасности (SO).

| Метод | Параметры (`args`) | Кто может вызывать |
|-------|--------------------|--------------------|
| **CertifyFirmware** | `id`, `securityObjectives` (массив строк, напр. `["SO_1","SO_2"]`) | CertCenter, admin |
| **ReadFirmware** | `id` | любой (чтение) |
| **ListFirmwares** | — | любой (чтение) |
| **UpdateFirmware** | `id`, `securityObjectives` (массив строк) | CertCenter, admin |
| **RevokeFirmwareCertification** | `id` | CertCenter, admin |

---

### OrderContract

Заказы на полёты и распределение платежей.

| Метод | Параметры (`args`) | Кто может вызывать |
|-------|--------------------|--------------------|
| **CreateOrder** | `id`, `aggregatorID`, `operatorID`, `droneID`, `insurerID`, `certCenterID`, `developerID`, `amountTotal` (int), `insuranceCoverageAmount` (int), `details` (массив объектов: `{drone_id, security_objectives[], environmental_limit[], operation_area}`) | Aggregator, admin |
| **AssignOrder** | `id`, `operatorID`, `droneID`, `details` (массив OrderDetail или пусто) | Aggregator, admin |
| **ApproveOrder** | `id` | Insurer, admin |
| **ConfirmOrder** | `id` | Operator, admin |
| **StartOrder** | `id` | Operator, admin |
| **FinishOrder** | `id` | Operator, admin |
| **FinalizeOrder** | `id` | Aggregator, admin |
| **DistributeFunds** | `id`, `distribution` (объект/map: ключ — id получателя, значение — `{recipient_id, amount}`), `notes` | Aggregator, admin |
| **ReadOrder** | `id` | любой (чтение) |
| **CheckDroneReadiness** | `droneID` | любой (чтение) |

---

### Сводка по организациям

| Организация (MSP) | Контракт | Действия |
|-------------------|----------|----------|
| **CertCenter** | DronePropertiesContract | Создание/обновление/удаление паспортов дронов |
| **CertCenter** | FirmwareContract | Сертификация, обновление, отзыв прошивок |
| **Insurer** | DronePropertiesContract | Создание и обновление статуса страховых записей |
| **Insurer** | OrderContract | Одобрение заказа (ApproveOrder) |
| **Aggregator** | OrderContract | Создание заказа, назначение, финализация, распределение средств |
| **Operator** | OrderContract | Подтверждение заказа, старт, завершение полёта |
| **Manufacturer** | — | Только чтение (паспорта, прошивки, заказы, готовность дрона) |
| **admin** (атрибут в сертификате) | Все контракты | Все методы, где в коде указан `roleAdmin` |

## Конфигурация

### Fabric Proxy (env)

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `FABRIC_PEER_ENDPOINT` | Адрес peer | `peer0.aggregator.drone-network.local:7051` |
| `FABRIC_MSP_ID` | MSP организации | `AggregatorMSP` |
| `FABRIC_CHANNEL` | Канал | `dronechannel` |
| `FABRIC_CHAINCODE` | Chaincode | `drone-chaincode` |
| `FABRIC_CRYPTO_PATH` | Путь к crypto-config | `/crypto` |
| `PORT` | Порт REST API | `3000` |

### docker/.env

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `ENABLE_FABRIC` | Включить Fabric-интеграцию | `false` |
| `FABRIC_PROXY_PORT` | Порт fabric-proxy на хосте | `3000` |

## Порядок запуска

1. **Fabric-сеть** (`./start.sh up`) — должна быть запущена первой
2. **sbd** (`make docker-up`) — fabric-proxy и ledger-gateway поднимутся автоматически

## Troubleshooting

- **fabric-proxy не подключается к peer** — проверьте, что Fabric-сеть запущена и сеть `fabric_drone` существует
- **ledger-gateway: fabric-proxy unavailable** — fabric-proxy ещё не стартовал, подождите или проверьте логи
- **gRPC TLS ошибка** — проверьте `crypto-config` в submodule

## E2E тестирование смарт-контрактов (dummy_fabric)

Система `dummy_fabric` (`systems/dummy_fabric/`) позволяет выполнить сквозной тест всех смарт-контрактов через реальную Fabric-сеть. Каждая организация (Aggregator, CertCenter, Insurer, Operator, Orvd) представлена отдельным компонентом со своим `fabric-proxy`, что обеспечивает корректную проверку ролей MSP.

### Архитектура

```
Компонент (Python) → HTTP → fabric-proxy-{org} (Go) → gRPC/TLS → Fabric Peer {org}
```

Каждый из 5 прокси настроен на свою организацию (`AggregatorMSP`, `CertCenterMSP`, `InsurerMSP`, `OperatorMSP`, `OrvdMSP`).

### Запуск

**1. Fabric-сеть должна быть запущена:**

```bash
cd fabric-network/network
./start.sh up
```

**2. Запуск dummy_fabric:**

```bash
cd systems/dummy_fabric
make docker-up
```

Будут подняты 5 fabric-proxy, 5 компонентов-организаций и gateway.

**3. Unit тесты (без Fabric, с моками):**

```bash
cd systems/dummy_fabric
make unit-test
```

**4. E2E тесты (требуют запущенную Fabric-сеть; и `docker-up`.**

```bash
make test-dummy-fabric (из корня проекта)
```

### Сценарий E2E теста

Полный workflow заказа (14 шагов):

| Шаг | Организация | Метод контракта |
|-----|-------------|-----------------|
| 1 | CertCenter | `FirmwareContract:CertifyFirmware` |
| 2 | CertCenter | `DronePropertiesContract:IssueTypeCertificate` |
| 3 | CertCenter | `DronePropertiesContract:CreateDronePass` |
| 4 | Insurer | `DronePropertiesContract:CreateInsuranceRecord` |
| 5 | Aggregator | `OrderContract:CreateOrder` |
| 6 | Aggregator | `OrderContract:AssignOrder` |
| 7 | Insurer | `OrderContract:ApproveOrder` |
| 8 | Operator | `OrderContract:ConfirmOrder` |
| 9 | Aggregator | `OrderContract:RequestFlightPermission` |
| 10 | Orvd | `OrderContract:ApproveFlightPermission` |
| 11 | Operator | `OrderContract:StartOrder` |
| 12 | Operator | `OrderContract:FinishOrder` |
| 13 | Aggregator | `OrderContract:FinalizeOrder` |
| 14 | Aggregator | `OrderContract:ReadOrder` (query — проверка финального статуса) |

Каждый шаг выполняется от имени соответствующей организации через её fabric-proxy, что гарантирует проверку ролей (MSP) на стороне chaincode.

### Переменные окружения для E2E тестов

При запуске E2E тестов вне Docker можно указать адреса proxy:

| Переменная | По умолчанию |
|------------|--------------|
| `FABRIC_PROXY_AGGREGATOR` | `http://localhost:3001` |
| `FABRIC_PROXY_CERTCENTER` | `http://localhost:3002` |
| `FABRIC_PROXY_INSURER` | `http://localhost:3003` |
| `FABRIC_PROXY_OPERATOR` | `http://localhost:3004` |
| `FABRIC_PROXY_ORVD` | `http://localhost:3005` |
