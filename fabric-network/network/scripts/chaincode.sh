#!/usr/bin/env bash

# Скрипт управления чейнкодом (смарт-контрактами)
# Drone Fleet Management System

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$(dirname "$NETWORK_DIR")"
CHANNEL_NAME="dronechannel"
CHAINCODE_NAME="drone-chaincode"
CHAINCODE_VERSION="1.0"
CHAINCODE_PATH="/opt/gopath/src/github.com/hyperledger/fabric/peer/chaincode"
CHAINCODE_LABEL="${CHAINCODE_NAME}_${CHAINCODE_VERSION}"
SEQUENCE=1

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Переменные
ORDERER_ADDRESS="orderer.drone-network.local:7050"
ORDERER_CA="/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/ordererOrganizations/drone-network.local/orderers/orderer.drone-network.local/msp/tlscacerts/tlsca.drone-network.local-cert.pem"

# Организации и их параметры (ОБНОВЛЕНО)
declare -A ORGS=(
    ["Aggregator"]="7051:aggregator.drone-network.local"
    ["Operator"]="8051:operator.drone-network.local"
    ["Insurer"]="9051:insurer.drone-network.local"
    ["CertCenter"]="10051:certcenter.drone-network.local"
    ["Manufacturer"]="11051:manufacturer.drone-network.local"
    ["Orvd"]="12051:orvd.drone-network.local"
    ["Regulator"]="13051:regulator.drone-network.local"
)

# Функция для установки переменных окружения организации
get_peer_env() {
    local org=$1
    local info=${ORGS[$org]}
    local port=$(echo $info | cut -d: -f1)
    local domain=$(echo $info | cut -d: -f2)
    
    echo "-e CORE_PEER_LOCALMSPID=${org}MSP \
        -e CORE_PEER_TLS_ROOTCERT_FILE=/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/${domain}/peers/peer0.${domain}/tls/ca.crt \
        -e CORE_PEER_MSPCONFIGPATH=/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/${domain}/users/Admin@${domain}/msp \
        -e CORE_PEER_ADDRESS=peer0.${domain}:${port}"
}

# Упаковка чейнкода
package_chaincode() {
    log_info "Упаковка чейнкода..."
    
    # Создаем tar архив с исходниками внутри CLI контейнера (без vendor)
    docker exec cli bash -c "
        cd /opt/gopath/src/github.com/hyperledger/fabric/peer/chaincode && \
        rm -rf vendor && \
        GO111MODULE=on go mod tidy && \
        cd /opt/gopath/src/github.com/hyperledger/fabric/peer && \
        peer lifecycle chaincode package ${CHAINCODE_NAME}.tar.gz \
            --path ${CHAINCODE_PATH} \
            --lang golang \
            --label ${CHAINCODE_LABEL}
    "
    
    log_success "Чейнкод упакован: ${CHAINCODE_NAME}.tar.gz"
}

# Установка чейнкода на пир
install_chaincode_on_peer() {
    local org=$1
    local env_vars=$(get_peer_env $org)
    
    log_info "Установка чейнкода на peer организации $org..."
    
    docker exec $env_vars cli peer lifecycle chaincode install ${CHAINCODE_NAME}.tar.gz
    
    log_success "Чейнкод установлен на peer $org"
}

# Установка чейнкода на все пиры
install_chaincode() {
    log_info "Установка чейнкода на все пиры..."
    
    for org in "${!ORGS[@]}"; do
        install_chaincode_on_peer $org
    done
    
    log_success "Чейнкод установлен на все пиры"
}

# Получение Package ID
get_package_id() {
    local env_vars=$(get_peer_env "Aggregator")
    
    docker exec $env_vars cli peer lifecycle chaincode queryinstalled \
        --output json | jq -r ".installed_chaincodes[] | select(.label==\"${CHAINCODE_LABEL}\") | .package_id"
}

# Одобрение чейнкода организацией
approve_chaincode() {
    local org=$1
    local package_id=$2
    local env_vars=$(get_peer_env $org)
    
    log_info "Одобрение чейнкода организацией $org..."
    
    docker exec $env_vars cli peer lifecycle chaincode approveformyorg \
        -o $ORDERER_ADDRESS \
        --channelID $CHANNEL_NAME \
        --name $CHAINCODE_NAME \
        --version $CHAINCODE_VERSION \
        --package-id $package_id \
        --sequence $SEQUENCE \
        --tls \
        --cafile $ORDERER_CA
    
    log_success "Чейнкод одобрен организацией $org"
}

# Одобрение чейнкода всеми организациями
approve_all() {
    log_info "Одобрение чейнкода всеми организациями..."
    
    local package_id=$(get_package_id)
    
    if [ -z "$package_id" ]; then
        log_error "Package ID не найден. Убедитесь, что чейнкод установлен."
        exit 1
    fi
    
    log_info "Package ID: $package_id"
    
    for org in "${!ORGS[@]}"; do
        approve_chaincode $org $package_id
        sleep 2
    done
    
    log_success "Чейнкод одобрен всеми организациями"
}

# Проверка готовности к коммиту
check_commit_readiness() {
    log_info "Проверка готовности к коммиту..."
    
    local env_vars=$(get_peer_env "Aggregator")
    
    docker exec $env_vars cli peer lifecycle chaincode checkcommitreadiness \
        --channelID $CHANNEL_NAME \
        --name $CHAINCODE_NAME \
        --version $CHAINCODE_VERSION \
        --sequence $SEQUENCE \
        --output json
}

# Коммит чейнкода
commit_chaincode() {
    log_info "Коммит чейнкода в канал..."
    
    local env_vars=$(get_peer_env "Aggregator")
    
    # Формируем список peer addresses для всех организаций
    local peer_addresses=""
    local tls_rootcerts=""
    
    for org in "${!ORGS[@]}"; do
        local info=${ORGS[$org]}
        local port=$(echo $info | cut -d: -f1)
        local domain=$(echo $info | cut -d: -f2)
        
        peer_addresses="$peer_addresses --peerAddresses peer0.${domain}:${port}"
        tls_rootcerts="$tls_rootcerts --tlsRootCertFiles /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/${domain}/peers/peer0.${domain}/tls/ca.crt"
    done
    
    docker exec $env_vars cli peer lifecycle chaincode commit \
        -o $ORDERER_ADDRESS \
        --channelID $CHANNEL_NAME \
        --name $CHAINCODE_NAME \
        --version $CHAINCODE_VERSION \
        --sequence $SEQUENCE \
        --tls \
        --cafile $ORDERER_CA \
        $peer_addresses \
        $tls_rootcerts
    
    log_success "Чейнкод закоммичен в канал"
}

# Проверка закоммиченного чейнкода
query_committed() {
    log_info "Проверка закоммиченного чейнкода..."
    
    local env_vars=$(get_peer_env "Aggregator")
    
    docker exec $env_vars cli peer lifecycle chaincode querycommitted \
        --channelID $CHANNEL_NAME \
        --name $CHAINCODE_NAME \
        --output json
}

# Тестовый вызов чейнкода
test_invoke() {
    log_info "Тестовый вызов чейнкода..."
    
    local env_vars=$(get_peer_env "Aggregator")
    
    # Формируем peer addresses
    local peer_addresses=""
    local tls_rootcerts=""
    
    for org in "${!ORGS[@]}"; do
        local info=${ORGS[$org]}
        local port=$(echo $info | cut -d: -f1)
        local domain=$(echo $info | cut -d: -f2)
        
        peer_addresses="$peer_addresses --peerAddresses peer0.${domain}:${port}"
        tls_rootcerts="$tls_rootcerts --tlsRootCertFiles /opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/${domain}/peers/peer0.${domain}/tls/ca.crt"
    done
    
    # Тестовый запрос - получение списка дронов
    docker exec $env_vars cli peer chaincode invoke \
        -o $ORDERER_ADDRESS \
        --channelID $CHANNEL_NAME \
        --name $CHAINCODE_NAME \
        -c '{"function":"DronePropertiesContract:ListDronePasses","Args":[]}' \
        --tls \
        --cafile $ORDERER_CA \
        $peer_addresses \
        $tls_rootcerts
    
    log_success "Тестовый вызов выполнен"
}

# Полное развертывание
deploy() {
    log_info "Полное развертывание чейнкода..."
    
    package_chaincode
    sleep 2
    
    install_chaincode
    sleep 3
    
    approve_all
    sleep 3
    
    check_commit_readiness
    sleep 2
    
    commit_chaincode
    sleep 2
    
    query_committed
    
    log_success "Чейнкод полностью развернут!"
    echo ""
    log_info "Теперь вы можете использовать чейнкод для:"
    log_info "  - DronePropertiesContract: управление паспортами дронов"
    log_info "  - SafetyObjectivesContract: управление целями безопасности"
    log_info "  - OrderContract: управление заказами и биллингом"
    log_info "  - Orvd: организация воздушного движения (добавлена)"
    log_info "  - Regulator: надзорный орган (добавлен)"
}

# Показать помощь
show_help() {
    echo ""
    echo "Управление чейнкодом (смарт-контрактами)"
    echo ""
    echo "Использование: $0 <команда>"
    echo ""
    echo "Команды:"
    echo "  package       Упаковать чейнкод"
    echo "  install       Установить на все пиры"
    echo "  approve       Одобрить всеми организациями"
    echo "  commit        Закоммитить в канал"
    echo "  query         Проверить закоммиченный чейнкод"
    echo "  test          Тестовый вызов"
    echo "  deploy        Полное развертывание (все шаги)"
    echo ""
}

# Главная логика
case "$1" in
    package)
        package_chaincode
        ;;
    install)
        install_chaincode
        ;;
    approve)
        approve_all
        ;;
    check)
        check_commit_readiness
        ;;
    commit)
        commit_chaincode
        ;;
    query)
        query_committed
        ;;
    test)
        test_invoke
        ;;
    deploy)
        deploy
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