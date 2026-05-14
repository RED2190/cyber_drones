#!/bin/bash

# Скрипт тестирования чейнкода в развёрнутой сети
# Drone Fleet Management System


SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK_DIR="$(dirname "$SCRIPT_DIR")"
CHANNEL_NAME="dronechannel"
CHAINCODE_NAME="drone-chaincode"

log_info() { echo "[INFO] $1"; }
log_success() { echo "[SUCCESS] $1"; }
log_error() { echo "[ERROR] $1"; }
log_test() { echo "[TEST] $1"; }

# Переменные для TLS
ORDERER_ADDRESS="orderer.drone-network.local:7050"
ORDERER_CA="/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/ordererOrganizations/drone-network.local/orderers/orderer.drone-network.local/msp/tlscacerts/tlsca.drone-network.local-cert.pem"

# Функция invoke для записи (с endorsement от 3 организаций для MAJORITY policy)
invoke() {
    local func=$1
    local args=$2
    local org=${3:-"Aggregator"}
    local port=${4:-7051}
    local domain=${5:-"aggregator.drone-network.local"}
    
    docker exec \
        -e CORE_PEER_LOCALMSPID="${org}MSP" \
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
        --peerAddresses peer0.certcenter.drone-network.local:10051 \
        --tlsRootCertFiles /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/certcenter.drone-network.local/peers/peer0.certcenter.drone-network.local/tls/ca.crt \
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

# ============ ТЕСТЫ ============

test_drone_pass() {
    echo ""
    echo "________ Тестирование DronePropertiesContract ________"
    echo ""
    
    # CreateDronePass params: id, developerID, model, droneType, weightKg, maxFlightRangeKm, maxPayloadWeightKg, releaseYear, incidentCount, firmwareID
    
    log_test "Создание паспорта дрона (ID: 1, Firmware: 1.0.1)"
    result=$(invoke "DronePropertiesContract:CreateDronePass" '["1","manufacturer-001","AG-100","agro","25","50","10","2024","0","1.0.1"]' "CertCenter" 10051 "certcenter.drone-network.local")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Паспорт дрона создан"
    else
        log_error "Ошибка: $result"
    fi
    sleep 2
    
    log_test "Чтение паспорта дрона (ID: 1)"
    result=$(query "DronePropertiesContract:ReadDronePass" '["1"]')
    echo "  Результат: $result"
    if echo "$result" | grep -q "AG-100"; then
        log_success "Паспорт успешно прочитан"
    else
        log_error "Паспорт не найден"
    fi
    
    log_test "Создание второго дрона (ID: 2, Firmware: 1.0.1)"
    result=$(invoke "DronePropertiesContract:CreateDronePass" '["2","manufacturer-001","AG-200","agro","30","60","15","2024","0","1.0.1"]' "CertCenter" 10051 "certcenter.drone-network.local")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Второй паспорт создан"
    else
        log_error "Ошибка: $result"
    fi
    sleep 2
    
    log_test "Создание третьего дрона (ID: 3, Firmware: 1.0.2)"
    result=$(invoke "DronePropertiesContract:CreateDronePass" '["3","manufacturer-002","AG-150","agro","20","45","8","2023","1","1.0.2"]' "CertCenter" 10051 "certcenter.drone-network.local")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Третий паспорт создан"
    else
        log_error "Ошибка: $result"
    fi
    sleep 2
    
    log_test "Получение списка всех дронов"
    result=$(query "DronePropertiesContract:ListDronePasses" '[]')
    echo "  Результат: $result"
    
    log_test "Обновление паспорта дрона (ID: 1)"
    result=$(invoke "DronePropertiesContract:UpdateDronePass" '["1","manufacturer-001","AG-100 Pro","agro","25","55","12","2025","0","1.0.1"]' "CertCenter" 10051 "certcenter.drone-network.local")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Паспорт обновлён"
    else
        log_error "Ошибка: $result"
    fi
    sleep 2
    
    result=$(query "DronePropertiesContract:ReadDronePass" '["1"]')
    echo "  Обновлённые данные: $result"
}

test_firmware() {
    echo ""
    echo "________ Тестирование FirmwareContract ________"
    echo ""
    
    log_test "Сертификация прошивки (ID: 1.0.1)"
    result=$(invoke "FirmwareContract:CertifyFirmware" '["1.0.1","[\"SO_1\",\"SO_3\",\"SO_7\",\"SO_9\"]"]' "CertCenter" 10051 "certcenter.drone-network.local")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Прошивка 1.0.1 сертифицирована"
    else
        log_error "Ошибка: $result"
    fi
    sleep 2
    
    log_test "Чтение прошивки (ID: 1.0.1)"
    result=$(query "FirmwareContract:ReadFirmware" '["1.0.1"]')
    echo "  Результат: $result"
    
    log_test "Сертификация прошивки (ID: 1.0.2)"
    result=$(invoke "FirmwareContract:CertifyFirmware" '["1.0.2","[\"SO_2\",\"SO_5\",\"SO_11\"]"]' "CertCenter" 10051 "certcenter.drone-network.local")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Прошивка 1.0.2 сертифицирована"
    else
        log_error "Ошибка: $result"
    fi
    sleep 2
    
    log_test "Получение списка всех прошивок"
    result=$(query "FirmwareContract:ListFirmwares" '[]')
    echo "  Результат: $result"
    
    log_test "Обновление прошивки (ID: 1.0.1)"
    result=$(invoke "FirmwareContract:UpdateFirmware" '["1.0.1","[\"SO_1\",\"SO_3\",\"SO_7\",\"SO_9\",\"SO_10\"]"]' "CertCenter" 10051 "certcenter.drone-network.local")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Прошивка обновлена"
    else
        log_error "Ошибка: $result"
    fi
    sleep 2
    
    result=$(query "FirmwareContract:ReadFirmware" '["1.0.1"]')
    echo "  Обновлённые данные: $result"
}

test_insurance() {
    echo ""
    echo "________ Тестирование Insurance ________"
    echo ""
    
    log_test "Создание страховки для дрона (ID: 1)"
    result=$(invoke "DronePropertiesContract:CreateInsuranceRecord" '["1","insurer-001","50000"]' "Insurer" 9051 "insurer.drone-network.local")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Страховка создана"
    else
        log_error "Ошибка: $result"
    fi
    sleep 2
    
    log_test "Чтение страховки (DroneID: 1)"
    result=$(query "DronePropertiesContract:ReadInsuranceRecord" '["1"]')
    echo "  Результат: $result"
    
    log_test "Создание страховки для дрона (ID: 2)"
    result=$(invoke "DronePropertiesContract:CreateInsuranceRecord" '["2","insurer-001","75000"]' "Insurer" 9051 "insurer.drone-network.local")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Страховка создана"
    else
        log_error "Ошибка: $result"
    fi
    sleep 2
    
    log_test "Обновление статуса страховки (DroneID: 1 -> expired)"
    result=$(invoke "DronePropertiesContract:UpdateInsuranceStatus" '["1","expired"]' "Insurer" 9051 "insurer.drone-network.local")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Статус страховки обновлён"
    else
        log_error "Ошибка: $result"
    fi
    sleep 2
    
    result=$(query "DronePropertiesContract:ReadInsuranceRecord" '["1"]')
    echo "  Обновлённые данные: $result"
}

test_readiness() {
    echo ""
    echo "________ Тестирование CheckDroneReadiness ________"
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

test_order_workflow() {
    echo ""
    echo "________ Тестирование OrderContract (Workflow) ________"
    echo ""
    
    local ORDER_ID="order-$(date +%s)"
    
    log_test "Шаг 1: Создание заказа (Aggregator)"
    result=$(invoke "OrderContract:CreateOrder" "[\"${ORDER_ID}\",\"agg-001\",\"\",\"\",\"ins-001\",\"cert-001\",\"dev-001\",\"81000\",\"5000\",\"23000\",\"20000\",\"355000\",\"[]\"]" "Aggregator" 7051 "aggregator.drone-network.local")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Заказ создан: $ORDER_ID"
    else
        log_error "Ошибка: $result"
        return 1
    fi
    sleep 2
    
    result=$(query "OrderContract:ReadOrder" "[\"${ORDER_ID}\"]")
    echo "  Статус после создания: $(echo $result | grep -o '"status":"[^"]*"')"
    
    log_test "Шаг 2: Назначение оператора и дрона (Aggregator)"
    result=$(invoke "OrderContract:AssignOrder" "[\"${ORDER_ID}\",\"op-001\",\"2\",\"[]\"]" "Aggregator" 7051 "aggregator.drone-network.local")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Оператор и дрон назначены"
    else
        log_error "Ошибка: $result"
    fi
    sleep 2
    
    result=$(query "OrderContract:ReadOrder" "[\"${ORDER_ID}\"]")
    echo "  Статус: $(echo $result | grep -o '"status":"[^"]*"')"
    
    log_test "Шаг 3: Одобрение заказа (Insurer)"
    result=$(invoke "OrderContract:ApproveOrder" "[\"${ORDER_ID}\"]" "Insurer" 9051 "insurer.drone-network.local")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Заказ одобрен страховщиком"
    else
        log_error "Ошибка: $result"
    fi
    sleep 2
    
    log_test "Шаг 4: Подтверждение заказа (Operator)"
    result=$(invoke "OrderContract:ConfirmOrder" "[\"${ORDER_ID}\"]" "Operator" 8051 "operator.drone-network.local")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Заказ подтверждён оператором"
    else
        log_error "Ошибка: $result"
    fi
    sleep 2
    
    log_test "Шаг 5: Начало выполнения (Operator)"
    result=$(invoke "OrderContract:StartOrder" "[\"${ORDER_ID}\"]" "Operator" 8051 "operator.drone-network.local")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Выполнение начато"
    else
        log_error "Ошибка: $result"
    fi
    sleep 2
    
    log_test "Шаг 6: Завершение выполнения (Operator)"
    result=$(invoke "OrderContract:FinishOrder" "[\"${ORDER_ID}\"]" "Operator" 8051 "operator.drone-network.local")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Выполнение завершено"
    else
        log_error "Ошибка: $result"
    fi
    sleep 2
    
    log_test "Шаг 7: Финализация заказа (Aggregator)"
    result=$(invoke "OrderContract:FinalizeOrder" "[\"${ORDER_ID}\"]" "Aggregator" 7051 "aggregator.drone-network.local")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Заказ финализирован"
    else
        log_error "Ошибка: $result"
    fi
    sleep 2
    
    echo ""
    log_info "Финальное состояние заказа:"
    result=$(query "OrderContract:ReadOrder" "[\"${ORDER_ID}\"]")
    echo "$result" | python3 -m json.tool 2>/dev/null || echo "$result"
}

test_billing_scenario() {
    echo ""
    echo "________ Тестирование финансового сценария ________"
    echo ""
    
    local ORDER_ID="order-billing-$(date +%s)"
    
    log_test "Создание заказа с финансовыми параметрами"
    result=$(invoke "OrderContract:CreateOrder" "[\"${ORDER_ID}\",\"agg-001\",\"op-001\",\"1\",\"ins-001\",\"cert-001\",\"dev-001\",\"81000\",\"5000\",\"23000\",\"20000\",\"355000\",\"[]\"]" "Aggregator" 7051 "aggregator.drone-network.local")
    if echo "$result" | grep -q "Chaincode invoke successful"; then
        log_success "Заказ создан: $ORDER_ID"
    else
        log_error "Ошибка: $result"
        return 1
    fi
    sleep 2
    
    log_test "Чтение заказа и распределения"
    result=$(query "OrderContract:ReadOrder" "[\"${ORDER_ID}\"]")
    echo "$result" | python3 -m json.tool 2>/dev/null || echo "$result"
}

run_all_tests() {
    echo ""
    echo "________ Тестирование смарт-контрактов Drone Fleet ________"
    echo ""
    
    test_drone_pass
    test_firmware
    test_insurance
    test_readiness
    test_billing_scenario
    test_order_workflow
    
    echo ""
    echo "________ Тестирование завершено ________"
    echo ""
}

show_help() {
    echo ""
    echo "Тестирование смарт-контрактов"
    echo ""
    echo "Использование: $0 [команда]"
    echo ""
    echo "Команды:"
    echo "  all        Запустить все тесты"
    echo "  drone      Тесты DronePropertiesContract"
    echo "  firmware   Тесты FirmwareContract"
    echo "  insurance  Тесты страхования"
    echo "  readiness  Тесты проверки готовности дрона"
    echo "  billing    Финансовый сценарий"
    echo "  order      Тесты OrderContract (workflow)"
    echo ""
}

case "${1:-all}" in
    all)
        run_all_tests
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
