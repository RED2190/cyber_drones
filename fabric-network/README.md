# Hyperledger Fabric Network - Drone Fleet Management

Сеть Hyperledger Fabric для системы управления парком дронов.

## Архитектура

### Организации

| Организация | Описание                            | Peer                                   | Порт |
| ---------------------- | ------------------------------------------- | -------------------------------------- | -------- |
| **Aggregator**   | Агрегатор заказов           | peer0.aggregator.drone-network.local   | 7051     |
| **Operator**     | Оператор дронов               | peer0.operator.drone-network.local     | 8051     |
| **Insurer**      | Страховщик                        | peer0.insurer.drone-network.local      | 9051     |
| **CertCenter**   | Сертификационный центр | peer0.certcenter.drone-network.local   | 10051    |
| **Manufacturer** | Производитель дронов     | peer0.manufacturer.drone-network.local | 11051    |

### Смарт-контракты (Chaincode)

1. **DronePropertiesContract** - Управление паспортами дронов

   - `CreateDronePass` - создание паспорта дрона
   - `ReadDronePass` - чтение паспорта
   - `UpdateDronePass` - обновление
   - `DeleteDronePass` - удаление
   - `ListDronePasses` - список всех паспортов
2. **SafetyObjectivesContract** - Управление целями безопасности

   - `CreateSafetyObjective` - создание цели безопасности
   - `UpdateSafetyObjective` - обновление
   - `ReadSafetyObjective` - чтение
   - `ListSafetyObjectivesForOrder` - список по заказу
   - `DeleteSafetyObjective` - удаление
3. **OrderContract** - Управление заказами и биллингом

   - `CreateOrder` - создание заказа
   - `AssignOrder` - назначение оператора и дрона
   - `ApproveOrder` - одобрение страховщиком
   - `ConfirmOrder` - подтверждение оператором
   - `StartOrder` / `FinishOrder` - начало/завершение
   - `FinalizeOrder` - финализация
   - `DistributeFunds` - распределение средств

### Роли

- `admin` - администратор (полный доступ)
- `aggregator` - агрегатор заказов
- `operator` - оператор дронов
- `insurer` - страховщик
- `cert_center` - сертификационный центр
- `manufacturer` - производитель

## Быстрый старт

### 1. Установка зависимостей

```bash
# Установка Fabric binaries и Docker images
./start.sh install
```

### 2. Запуск сети

```bash
# Полный запуск (генерация + сеть + канал + чейнкод)
./start.sh up
```

### 3. Проверка статуса

```bash
./start.sh status
```

### 4. Остановка сети

```bash
./start.sh down
```

## Пошаговый запуск

Если нужен более детальный контроль:

```bash
# 1. Генерация криптоматериалов
./scripts/generate.sh

# 2. Запуск Docker контейнеров
./scripts/network.sh up

# 3. Создание и настройка канала
./scripts/channel.sh setup

# 4. Развертывание чейнкода
./scripts/chaincode.sh deploy
```

## Команды управления

### Сеть

```bash
./start.sh up        # Запуск
./start.sh down      # Остановка
./start.sh restart   # Перезапуск
./start.sh status    # Статус
./start.sh logs      # Логи всех контейнеров
./start.sh logs orderer.drone-network.local  # Логи конкретного контейнера
./start.sh clean     # Полная очистка
```

### Канал

```bash
./scripts/channel.sh create   # Создать канал
./scripts/channel.sh join     # Присоединить пиры
./scripts/channel.sh anchors  # Обновить anchor peers
./scripts/channel.sh info     # Информация о канале
```

### Чейнкод

```bash
./scripts/chaincode.sh package   # Упаковать
./scripts/chaincode.sh install   # Установить
./scripts/chaincode.sh approve   # Одобрить
./scripts/chaincode.sh commit    # Закоммитить
./scripts/chaincode.sh query     # Проверить
./scripts/chaincode.sh test      # Тестовый вызов
./scripts/chaincode.sh deploy    # Полное развертывание
```

## Требования

- Docker 20.10+
- Docker Compose 2.0+
- Go 1.21+ (для сборки чейнкода)
- jq (для обработки JSON)
- curl

## Структура файлов

```
network/
├── channel-artifacts/     # Артефакты канала (генерируются)
├── crypto-config/         # Криптоматериалы (генерируются)
├── scripts/
│   ├── generate.sh        # Генерация криптоматериалов
│   ├── network.sh         # Управление сетью
│   ├── channel.sh         # Управление каналом
│   ├── chaincode.sh       # Управление чейнкодом
│   └── install-fabric.sh  # Установка Fabric
├── configtx.yaml          # Конфигурация канала
├── crypto-config.yaml     # Конфигурация криптоматериалов
├── docker-compose.yaml    # Docker Compose конфигурация
└── start.sh               # Главный скрипт запуска
```

## Порты

| Сервис           | Порт |
| ---------------------- | -------- |
| Orderer                | 7050     |
| Orderer Admin          | 7053     |
| Aggregator Peer        | 7051     |
| Operator Peer          | 8051     |
| Insurer Peer           | 9051     |
| CertCenter Peer        | 10051    |
| Manufacturer Peer      | 11051    |
| Metrics (Aggregator)   | 9444     |
| Metrics (Operator)     | 9445     |
| Metrics (Insurer)      | 9446     |
| Metrics (CertCenter)   | 9447     |
| Metrics (Manufacturer) | 9448     |

## Пример вызова чейнкода

### Создание паспорта дрона (из CLI контейнера)

```bash
docker exec \
  -e CORE_PEER_LOCALMSPID="CertCenterMSP" \
  -e CORE_PEER_TLS_ROOTCERT_FILE="/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/certcenter.drone-network.local/peers/peer0.certcenter.drone-network.local/tls/ca.crt" \
  -e CORE_PEER_MSPCONFIGPATH="/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/certcenter.drone-network.local/users/Admin@certcenter.drone-network.local/msp" \
  -e CORE_PEER_ADDRESS="peer0.certcenter.drone-network.local:10051" \
  cli peer chaincode invoke \
  -o orderer.drone-network.local:7050 \
  --channelID dronechannel \
  --name drone-chaincode \
  -c '{"function":"DronePropertiesContract:CreateDronePass","Args":["1","manufacturer-001","DJI Mavic 3"]}' \
  --tls \
  --cafile /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/ordererOrganizations/drone-network.local/orderers/orderer.drone-network.local/msp/tlscacerts/tlsca.drone-network.local-cert.pem \
  --peerAddresses peer0.certcenter.drone-network.local:10051 \
  --tlsRootCertFiles /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/certcenter.drone-network.local/peers/peer0.certcenter.drone-network.local/tls/ca.crt \
  --peerAddresses peer0.aggregator.drone-network.local:7051 \
  --tlsRootCertFiles /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/aggregator.drone-network.local/peers/peer0.aggregator.drone-network.local/tls/ca.crt \
  --peerAddresses peer0.operator.drone-network.local:8051 \
  --tlsRootCertFiles /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/operator.drone-network.local/peers/peer0.operator.drone-network.local/tls/ca.crt
```

### Получение списка дронов

```bash
docker exec cli peer chaincode query \
  --channelID dronechannel \
  --name drone-chaincode \
  -c '{"function":"DronePropertiesContract:ListDronePasses","Args":[]}'
```

## Устранение неполадок

### Контейнеры не запускаются

```bash
# Проверьте логи
docker logs orderer.drone-network.local
docker logs peer0.aggregator.drone-network.local

# Полная очистка и перезапуск
./start.sh clean
./start.sh up
```

### Ошибка "cryptogen not found"

```bash
source ~/.bashrc
export PATH=$PATH:/home/$USER/fabric/bin
```
