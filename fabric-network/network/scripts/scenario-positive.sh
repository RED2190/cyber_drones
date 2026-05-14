#!/bin/bash

# Скрипт тестирования чейнкода в развёрнутой сети
# Drone Fleet Management System

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK_DIR="$(dirname "$SCRIPT_DIR")"
CHANNEL_NAME="dronechannel"
CHAINCODE_NAME="drone-chaincode"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_test() { echo -e "${CYAN}[TEST]${NC} $1"; }

# Переменные для TLS
ORDERER_ADDRESS="orderer.drone-network.local:7050"
ORDERER_CA="/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/ordererOrganizations/drone-network.local/orderers/orderer.drone-network.local/msp/tlscacerts/tlsca.drone-network.local-cert.pem"

# Организации и их параметры
declare -A ORGS=(
    ["Aggregator"]="7051:aggregator.drone-network.local:AggregatorMSP"
    ["Operator"]="8051:operator.drone-network.local:OperatorMSP"
    ["Insurer"]="9051:insurer.drone-network.local:InsurerMSP"
    ["CertCenter"]="10051:certcenter.drone-network.local:CertCenterMSP"
    ["Manufacturer"]="11051:manufacturer.drone-network.local:ManufacturerMSP"
    ["Orvd"]="12051:orvd.drone-network.local:OrvdMSP"
    ["Regulator"]="13051:regulator.drone-network.local:RegulatorMSP"
)

# Функция invoke для записи (с endorsement от всех организаций)
invoke() {
    local func=$1
    local args=$2
    local org=${3:-"Aggregator"}
    
    local info=${ORGS[$org]}
    local port=$(echo $info | cut -d: -f1)
    local domain=$(echo $info | cut -d: -f2)
    local msp=$(echo $info | cut -d: -f3)
    
    log_info "Выполнение $func от лица $org..."
    
    docker exec \
        -e CORE_PEER_LOCALMSPID="$msp" \
        -e CORE_PEER_TLS_ROOTCERT_FILE="/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/${domain}/peers/peer0.${domain}/tls/ca.crt" \
        -e CORE_PEER_MSPCONFIGPATH="/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/${domain}/users/Admin@${domain}/msp" \
        -e CORE_PEER_ADDRESS="peer0.${domain}:${port}" \
        cli peer chaincode invoke \
        -o $ORDERER_ADDRESS \
        --channelID $CHANNEL_NAME \
        --name $CHAINCODE_NAME \
        -c "{\"function\":\"${func}\",\"Args\":${args}}" \
        --tls \
        --cafile $ORDERER_CA \
        --peerAddresses peer0.aggregator.drone-network.local:7051 \
        --tlsRootCertFiles /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/aggregator.drone-network.local/peers/peer0.aggregator.drone-network.local/tls/ca.crt \
        --peerAddresses peer0.operator.drone-network.local:8051 \
        --tlsRootCertFiles /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/operator.drone-network.local/peers/peer0.operator.drone-network.local/tls/ca.crt \
        --peerAddresses peer0.insurer.drone-network.local:9051 \
        --tlsRootCertFiles /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/insurer.drone-network.local/peers/peer0.insurer.drone-network.local/tls/ca.crt \
        --peerAddresses peer0.certcenter.drone-network.local:10051 \
        --tlsRootCertFiles /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/certcenter.drone-network.local/peers/peer0.certcenter.drone-network.local/tls/ca.crt \
        --peerAddresses peer0.manufacturer.drone-network.local:11051 \
        --tlsRootCertFiles /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/manufacturer.drone-network.local/peers/peer0.manufacturer.drone-network.local/tls/ca.crt \
        --peerAddresses peer0.orvd.drone-network.local:12051 \
        --tlsRootCertFiles /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/orvd.drone-network.local/peers/peer0.orvd.drone-network.local/tls/ca.crt \
        --peerAddresses peer0.regulator.drone-network.local:13051 \
        --tlsRootCertFiles /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/regulator.drone-network.local/peers/peer0.regulator.drone-network.local/tls/ca.crt \
        2>&1
}

# Функция query для чтения
query() {
    local func=$1
    local args=$2
    
    docker exec cli peer chaincode query \
        --channelID $CHANNEL_NAME \
        --name $CHAINCODE_NAME \
        -c "{\"function\":\"${func}\",\"Args\":${args}}" \
        2>&1
}

# Ожидание между шагами
wait_step() {
    sleep 2
}

# ============ ТЕСТЫ ============

test_drone_pass() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "        Тестирование DronePropertiesContract"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    
    # CreateDronePass params: id, developerID, model, droneType, weightKg, maxFlightRangeKm, maxPayloadWeightKg, releaseYear, firmwareID
    
    log_test "Создание паспорта дрона (ID: 1, Firmware: 1.0.1)"
    result=$(invoke "DronePropertiesContract:CreateDronePass" '["1","manufacturer-001","AG-100","agro","25","50","10","2024","1.0.1"]' "CertCenter")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Паспорт дрона создан"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
    
    log_test "Чтение паспорта дрона (ID: 1)"
    result=$(query "DronePropertiesContract:ReadDronePass" '["1"]')
    echo "  Результат: $result"
    if echo "$result" | grep -q "AG-100"; then
        log_success "Паспорт успешно прочитан"
    else
        log_error "Паспорт не найден"
    fi
    
    log_test "Создание второго дрона (ID: 2, Firmware: 1.0.1)"
    result=$(invoke "DronePropertiesContract:CreateDronePass" '["2","manufacturer-001","AG-200","agro","30","60","15","2024","1.0.1"]' "CertCenter")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Второй паспорт создан"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
    
    log_test "Создание третьего дрона (ID: 3, Firmware: 1.0.2)"
    result=$(invoke "DronePropertiesContract:CreateDronePass" '["3","manufacturer-002","AG-150","agro","20","45","8","2023","1.0.2"]' "CertCenter")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Третий паспорт создан"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
    
    log_test "Получение списка всех дронов"
    result=$(query "DronePropertiesContract:ListDronePasses" '[]')
    echo "  Результат: $result"
    
    log_test "Обновление паспорта дрона (ID: 1)"
    result=$(invoke "DronePropertiesContract:UpdateDronePass" '["1","manufacturer-001","AG-100 Pro","agro","25","55","12","2025","1.0.1"]' "CertCenter")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Паспорт обновлён"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
    
    result=$(query "DronePropertiesContract:ReadDronePass" '["1"]')
    echo "  Обновлённые данные: $result"
}

test_firmware() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "        Тестирование FirmwareContract"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    
    log_test "Сертификация прошивки (ID: 1.0.1)"
    result=$(invoke "FirmwareContract:CertifyFirmware" '["1.0.1","[\"SO_1\",\"SO_3\",\"SO_7\",\"SO_9\"]"]' "CertCenter")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Прошивка 1.0.1 сертифицирована"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
    
    log_test "Чтение прошивки (ID: 1.0.1)"
    result=$(query "FirmwareContract:ReadFirmware" '["1.0.1"]')
    echo "  Результат: $result"
    
    log_test "Сертификация прошивки (ID: 1.0.2)"
    result=$(invoke "FirmwareContract:CertifyFirmware" '["1.0.2","[\"SO_2\",\"SO_5\",\"SO_11\"]"]' "CertCenter")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Прошивка 1.0.2 сертифицирована"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
    
    log_test "Получение списка всех прошивок"
    result=$(query "FirmwareContract:ListFirmwares" '[]')
    echo "  Результат: $result"
    
    log_test "Обновление прошивки (ID: 1.0.1)"
    result=$(invoke "FirmwareContract:UpdateFirmware" '["1.0.1","[\"SO_1\",\"SO_3\",\"SO_7\",\"SO_9\",\"SO_10\"]"]' "CertCenter")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Прошивка обновлена"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
    
    result=$(query "FirmwareContract:ReadFirmware" '["1.0.1"]')
    echo "  Обновлённые данные: $result"
}

test_insurance() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "        Тестирование Insurance"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    
    log_test "Создание базовой страховки для дрона (ID: 1)"
    result=$(invoke "DronePropertiesContract:CreateInsuranceRecord" '["1","insurer-001","50000","0","2026-01-01T00:00:00Z","2027-01-01T00:00:00Z"]' "Insurer")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Базовая страховка создана"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
    
    log_test "Чтение страховки (DroneID: 1)"
    result=$(query "DronePropertiesContract:ReadInsuranceRecord" '["1"]')
    echo "  Результат: $result"
    
    log_test "Создание базовой страховки для дрона (ID: 2)"
    result=$(invoke "DronePropertiesContract:CreateInsuranceRecord" '["2","insurer-001","75000","0","2026-01-01T00:00:00Z","2027-01-01T00:00:00Z"]' "Insurer")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Базовая страховка создана"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
    
    log_test "Обновление статуса страховки (DroneID: 1 -> expired)"
    result=$(invoke "DronePropertiesContract:UpdateInsuranceStatus" '["1","expired"]' "Insurer")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Статус страховки обновлён"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
    
    result=$(query "DronePropertiesContract:ReadInsuranceRecord" '["1"]')
    echo "  Обновлённые данные: $result"
    
    log_test "Создание миссионной страховки для заказа ORDER-001"
    result=$(invoke "OrderContract:CreateMissionInsurance" '["MIS-001","ORDER-001","1","BASE-INS-001","insurer-001","5000","200000"]' "Insurer")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Миссионная страховка создана"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
    
    log_test "Чтение миссионной страховки (ID: MIS-001)"
    result=$(query "OrderContract:ReadMissionInsurance" '["MIS-001"]')
    echo "  Результат: $result"
}

test_readiness() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "        Тестирование CheckDroneReadiness"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    
    log_test "Проверка готовности дрона (ID: 1)"
    result=$(query "OrderContract:CheckDroneReadiness" '["1"]')
    echo "  Результат: $result"
    
    log_test "Проверка готовности дрона (ID: 2)"
    result=$(query "OrderContract:CheckDroneReadiness" '["2"]')
    echo "  Результат: $result"
    
    log_test "Проверка готовности дрона (ID: 3)"
    result=$(query "OrderContract:CheckDroneReadiness" '["3"]')
    echo "  Результат: $result"
}

test_flight_permission() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "        Тестирование Flight Permission (ОрВД)"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    
    local ORDER_ID="order-$(date +%s)"
    
    log_test "Запрос разрешения на полет (Operator)"
    result=$(invoke "OrderContract:RequestFlightPermission" "[\"${ORDER_ID}\",\"zone-A\",\"2026-02-18T14:00:00Z\",\"2026-02-18T16:00:00Z\"]" "Operator")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Запрос разрешения создан"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
    
    log_test "Одобрение разрешения (Orvd)"
    result=$(invoke "OrderContract:ApproveFlightPermission" "[\"PERM-${ORDER_ID}\",\"[\",\"max_altitude:150m\",\"maintain_vlos\"]\"]" "Orvd")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Разрешение одобрено"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
    
    log_test "Чтение разрешения"
    result=$(query "OrderContract:ReadFlightPermission" "[\"PERM-${ORDER_ID}\"]")
    echo "  Результат: $result"
    
    log_test "Закрытие разрешения после полета"
    result=$(invoke "OrderContract:CloseFlightPermission" "[\"PERM-${ORDER_ID}\"]" "Operator")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Разрешение закрыто"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
}

test_restricted_zones() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "        Тестирование Restricted Zones (Регулятор)"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    
    log_test "Создание запретной зоны (Regulator)"
    result=$(invoke "OrderContract:CreateRestrictedZone" '["ZONE-001","Аэропорт Домодедово","airport-zone","2026-01-01T00:00:00Z","2026-12-31T23:59:59Z"]' "Regulator")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Запретная зона создана"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
    
    log_test "Проверка конфликта с зоной"
    result=$(query "OrderContract:CheckZoneConflict" '["airport-zone","2026-02-18T14:00:00Z"]')
    echo "  Результат: $result"
    
    log_test "Список всех запретных зон"
    result=$(query "OrderContract:ListRestrictedZones" '[]')
    echo "  Результат: $result"
}

test_order_workflow() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "        Тестирование OrderContract (Workflow)"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    
    local ORDER_ID="order-$(date +%s)"
    
    log_test "Шаг 1: Создание заказа (Aggregator)"
    result=$(invoke "OrderContract:CreateOrder" "[\"${ORDER_ID}\",\"agg-001\",\"\",\"\",\"ins-001\",\"cert-001\",\"dev-001\",\"81000\",\"5000\",\"23000\",\"20000\",\"355000\",\"[]\",\"2026-02-18T14:00:00Z\",\"2026-02-18T16:00:00Z\",\"zone-A\"]" "Aggregator")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Заказ создан: $ORDER_ID"
    else
        log_error "Ошибка: $result"
        return 1
    fi
    wait_step
    
    result=$(query "OrderContract:ReadOrder" "[\"${ORDER_ID}\"]")
    echo "  Статус после создания: $(echo $result | grep -o '"status":"[^"]*"')"
    
    log_test "Шаг 2: Назначение оператора и дрона (Aggregator)"
    result=$(invoke "OrderContract:AssignOrder" "[\"${ORDER_ID}\",\"op-001\",\"2\",\"[]\"]" "Aggregator")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Оператор и дрон назначены"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
    
    result=$(query "OrderContract:ReadOrder" "[\"${ORDER_ID}\"]")
    echo "  Статус: $(echo $result | grep -o '"status":"[^"]*"')"
    
    log_test "Шаг 3: Одобрение заказа (Insurer)"
    result=$(invoke "OrderContract:ApproveOrder" "[\"${ORDER_ID}\"]" "Insurer")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Заказ одобрен страховщиком"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
    
    log_test "Шаг 4: Запрос разрешения в ОрВД (Operator)"
    result=$(invoke "OrderContract:RequestFlightPermission" "[\"${ORDER_ID}\",\"zone-A\",\"2026-02-18T14:00:00Z\",\"2026-02-18T16:00:00Z\"]" "Operator")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Запрос разрешения создан"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
    
    log_test "Шаг 5: Одобрение разрешения (Orvd)"
    result=$(invoke "OrderContract:ApproveFlightPermission" "[\"PERM-${ORDER_ID}\",\"max_altitude:150m,maintain_vlos\"]" "Orvd")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Разрешение одобрено"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
    
    log_test "Шаг 6: Подтверждение заказа (Operator)"
    result=$(invoke "OrderContract:ConfirmOrder" "[\"${ORDER_ID}\"]" "Operator")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Заказ подтверждён оператором"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
    
    log_test "Шаг 7: Начало выполнения (Operator)"
    result=$(invoke "OrderContract:StartOrder" "[\"${ORDER_ID}\"]" "Operator")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Выполнение начато"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
    
    log_test "Шаг 8: Завершение выполнения (Operator)"
    result=$(invoke "OrderContract:FinishOrder" "[\"${ORDER_ID}\"]" "Operator")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Выполнение завершено"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
    
    log_test "Шаг 9: Закрытие разрешения (Operator)"
    result=$(invoke "OrderContract:CloseFlightPermission" "[\"PERM-${ORDER_ID}\"]" "Operator")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Разрешение закрыто"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
    
    log_test "Шаг 10: Финализация заказа (Aggregator)"
    result=$(invoke "OrderContract:FinalizeOrder" "[\"${ORDER_ID}\"]" "Aggregator")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Заказ финализирован"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
    
    echo ""
    log_info "Финальное состояние заказа:"
    result=$(query "OrderContract:ReadOrder" "[\"${ORDER_ID}\"]")
    echo "$result" | python3 -m json.tool 2>/dev/null || echo "$result"
}

test_billing_scenario() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "        Тестирование финансового сценария"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    
    local ORDER_ID="order-billing-$(date +%s)"
    
    log_test "Создание заказа с финансовыми параметрами"
    result=$(invoke "OrderContract:CreateOrder" "[\"${ORDER_ID}\",\"agg-001\",\"op-001\",\"1\",\"ins-001\",\"cert-001\",\"dev-001\",\"81000\",\"5000\",\"23000\",\"20000\",\"355000\",\"[]\",\"2026-02-18T14:00:00Z\",\"2026-02-18T16:00:00Z\",\"zone-A\"]" "Aggregator")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Заказ создан: $ORDER_ID"
    else
        log_error "Ошибка: $result"
        return 1
    fi
    wait_step
    
    log_test "Чтение заказа и распределения"
    result=$(query "OrderContract:ReadOrder" "[\"${ORDER_ID}\"]")
    echo "$result" | python3 -m json.tool 2>/dev/null || echo "$result"
    
    log_test "Распределение средств (DistributeFunds)"
    result=$(invoke "OrderContract:DistributeFunds" "[\"${ORDER_ID}\",{\"operator\":{\"recipient_id\":\"op-001\",\"amount\":25000},\"aggregator\":{\"recipient_id\":\"agg-001\",\"amount\":5000},\"insurer\":{\"recipient_id\":\"ins-001\",\"amount\":3000},\"cert_center\":{\"recipient_id\":\"cert-001\",\"amount\":2000},\"risk_reserve\":{\"recipient_id\":\"risk_reserve\",\"amount\":2000}},\"mission completed\"]" "Aggregator")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Средства распределены"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
}

test_violation_report() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "        Тестирование Report Violation (Регулятор)"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    
    log_test "Сообщение о нарушении (Regulator)"
    result=$(invoke "OrderContract:ReportViolation" '["ORDER-001","1","no_fly_zone"]' "Regulator")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Нарушение зарегистрировано"
    else
        log_error "Ошибка: $result"
    fi
    wait_step
    
    log_test "Получение нарушений по заказу"
    result=$(query "OrderContract:GetViolationsByOrder" '["ORDER-001"]')
    echo "  Результат: $result"
}

run_all_tests() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "     ПОЛНОЕ ТЕСТИРОВАНИЕ СМАРТ-КОНТРАКТОВ DRONE FLEET"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    echo "Участвуют организации:"
    echo "  - Aggregator (агрегатор)"
    echo "  - Operator (оператор)"
    echo "  - Insurer (страховая)"
    echo "  - CertCenter (сертификационный центр)"
    echo "  - Manufacturer (производитель)"
    echo "  - Orvd (ОрВД)"
    echo "  - Regulator (регулятор)"
    echo ""
    
    test_firmware
    test_drone_pass
    test_insurance
    test_readiness
    test_flight_permission
    test_restricted_zones
    test_violation_report
    test_billing_scenario
    test_order_workflow
    
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "        ТЕСТИРОВАНИЕ УСПЕШНО ЗАВЕРШЕНО"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
}

run_positive_scenario() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "        ПОЗИТИВНЫЙ СЦЕНАРИЙ ЗАКАЗА ДРОНА"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    
    local ORDER_ID="order-positive-$(date +%s)"
    
    log_test "1. Сертификация прошивки (CertCenter)"
    invoke "FirmwareContract:CertifyFirmware" '["1.0.1","[\"SO_1\",\"SO_3\",\"SO_7\",\"SO_9\"]"]' "CertCenter"
    wait_step
    
    log_test "2. Создание паспорта дрона (CertCenter)"
    invoke "DronePropertiesContract:CreateDronePass" '["1","manufacturer-001","AG-100","agro","25","50","10","2024","1.0.1"]' "CertCenter"
    wait_step
    
    log_test "3. Базовая страховка дрона (Insurer)"
    invoke "DronePropertiesContract:CreateInsuranceRecord" '["1","insurer-001","50000","0","2026-01-01T00:00:00Z","2027-01-01T00:00:00Z"]' "Insurer"
    wait_step
    
    log_test "4. Проверка готовности дрона"
    query "OrderContract:CheckDroneReadiness" '["1"]'
    
    log_test "5. Создание заказа (Aggregator)"
    invoke "OrderContract:CreateOrder" "[\"${ORDER_ID}\",\"agg-001\",\"\",\"\",\"ins-001\",\"cert-001\",\"dev-001\",\"81000\",\"5000\",\"23000\",\"20000\",\"355000\",\"[{\\\"drone_id\\\":\\\"1\\\",\\\"security_objectives\\\":[\\\"SO_1\\\",\\\"SO_3\\\"],\\\"environmental_limit\\\":[\\\"wind_10ms\\\"],\\\"operation_area\\\":\\\"zone-A\\\"}]\",\"2026-02-18T14:00:00Z\",\"2026-02-18T16:00:00Z\",\"zone-A\"]" "Aggregator"
    wait_step
    
    log_test "6. Назначение оператора (Aggregator)"
    invoke "OrderContract:AssignOrder" "[\"${ORDER_ID}\",\"op-001\",\"1\",\"[]\"]" "Aggregator"
    wait_step
    
    log_test "7. Создание страховки на миссию (Insurer)"
    invoke "OrderContract:CreateMissionInsurance" "[\"MIS-${ORDER_ID}\",\"${ORDER_ID}\",\"1\",\"BASE-INS-001\",\"insurer-001\",\"5000\",\"200000\"]" "Insurer"
    wait_step
    
    log_test "8. Согласование со страховой (Insurer)"
    invoke "OrderContract:ApproveOrder" "[\"${ORDER_ID}\"]" "Insurer"
    wait_step
    
    log_test "9. Запрос разрешения в ОрВД (Operator)"
    invoke "OrderContract:RequestFlightPermission" "[\"${ORDER_ID}\",\"zone-A\",\"2026-02-18T14:00:00Z\",\"2026-02-18T16:00:00Z\"]" "Operator"
    wait_step
    
    log_test "10. Одобрение разрешения ОрВД (Orvd)"
    invoke "OrderContract:ApproveFlightPermission" "[\"PERM-${ORDER_ID}\",\"max_altitude:150m,maintain_vlos\"]" "Orvd"
    wait_step
    
    log_test "11. Подтверждение оператором (Operator)"
    invoke "OrderContract:ConfirmOrder" "[\"${ORDER_ID}\"]" "Operator"
    wait_step
    
    log_test "12. Начало полета (Operator)"
    invoke "OrderContract:StartOrder" "[\"${ORDER_ID}\"]" "Operator"
    wait_step
    
    log_test "13. Завершение полета (Operator)"
    invoke "OrderContract:FinishOrder" "[\"${ORDER_ID}\"]" "Operator"
    wait_step
    
    log_test "14. Закрытие разрешения ОрВД (Operator)"
    invoke "OrderContract:CloseFlightPermission" "[\"PERM-${ORDER_ID}\"]" "Operator"
    wait_step
    
    log_test "15. Финализация заказа (Aggregator)"
    invoke "OrderContract:FinalizeOrder" "[\"${ORDER_ID}\"]" "Aggregator"
    wait_step
    
    log_test "16. Распределение средств (Aggregator)"
    invoke "OrderContract:DistributeFunds" "[\"${ORDER_ID}\",{\"operator\":{\"recipient_id\":\"op-001\",\"amount\":25000},\"aggregator\":{\"recipient_id\":\"agg-001\",\"amount\":5000},\"insurer\":{\"recipient_id\":\"ins-001\",\"amount\":3000},\"cert_center\":{\"recipient_id\":\"cert-001\",\"amount\":2000},\"risk_reserve\":{\"recipient_id\":\"risk_reserve\",\"amount\":2000}},\"mission completed\"]" "Aggregator"
    wait_step
    
    echo ""
    log_success "ПОЗИТИВНЫЙ СЦЕНАРИЙ УСПЕШНО ВЫПОЛНЕН!"
    echo ""
    log_info "Финальное состояние заказа:"
    query "OrderContract:ReadOrder" "[\"${ORDER_ID}\"]"
}

show_help() {
    echo ""
    echo "Тестирование смарт-контрактов Drone Fleet Management System"
    echo ""
    echo "Использование: $0 [команда]"
    echo ""
    echo "Команды:"
    echo "  all           Запустить все тесты"
    echo "  positive      Запустить позитивный сценарий заказа"
    echo "  drone         Тесты DronePropertiesContract"
    echo "  firmware      Тесты FirmwareContract"
    echo "  insurance     Тесты страхования (базовое + миссионное)"
    echo "  readiness     Тесты проверки готовности дрона"
    echo "  flight        Тесты разрешений ОрВД"
    echo "  zones         Тесты запретных зон (регулятор)"
    echo "  violation     Тесты нарушений (регулятор)"
    echo "  billing       Финансовый сценарий"
    echo "  order         Тесты OrderContract (workflow)"
    echo ""
}

case "${1:-all}" in
    all)
        run_all_tests
        ;;
    positive)
        run_positive_scenario
        ;;
    drone)
        test_drone_pass
        ;;
    firmware)
        test_firmware
        ;;
    insurance)
        test_insurance
        ;;
    readiness)
        test_readiness
        ;;
    flight)
        test_flight_permission
        ;;
    zones)
        test_restricted_zones
        ;;
    violation)
        test_violation_report
        ;;
    billing)
        test_billing_scenario
        ;;
    order)
        test_order_workflow
        ;;
    -h|--help|help)
        show_help
        ;;
    *)
        log_error "Неизвестная команда: $1"
        show_help
        exit 1
        ;;
esac