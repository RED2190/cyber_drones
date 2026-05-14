#!/bin/bash

# Скрипт генерации криптографических материалов и артефактов канала
# Drone Fleet Management - Hyperledger Fabric Network

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK_DIR="$(dirname "$SCRIPT_DIR")"
CHANNEL_NAME="dronechannel"

export FABRIC_CFG_PATH="$NETWORK_DIR"

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

# Проверка наличия необходимых инструментов
check_prerequisites() {
    log_info "Проверка необходимых инструментов..."
    
    if ! command -v cryptogen &> /dev/null; then
        log_error "cryptogen не найден. Установите Hyperledger Fabric binaries."
        log_info "Выполните: curl -sSL https://bit.ly/2ysbOFE | bash -s -- 2.5.4 1.5.7 -s"
        exit 1
    fi
    
    if ! command -v configtxgen &> /dev/null; then
        log_error "configtxgen не найден. Установите Hyperledger Fabric binaries."
        exit 1
    fi
    
    log_success "Все необходимые инструменты найдены"
}

# Очистка предыдущих артефактов
clean() {
    log_info "Очистка предыдущих артефактов..."
    rm -rf "$NETWORK_DIR/crypto-config"
    rm -rf "$NETWORK_DIR/channel-artifacts"
    log_success "Очистка завершена"
}

# Генерация криптографических материалов
generate_crypto() {
    log_info "Генерация криптографических материалов..."
    
    cd "$NETWORK_DIR"
    
    cryptogen generate --config=./crypto-config.yaml --output=./crypto-config
    
    if [ $? -ne 0 ]; then
        log_error "Ошибка при генерации криптоматериалов"
        exit 1
    fi
    
    log_success "Криптографические материалы сгенерированы"
}

# Генерация генезис-блока и артефактов канала
generate_channel_artifacts() {
    log_info "Генерация артефактов канала..."
    
    mkdir -p "$NETWORK_DIR/channel-artifacts"
    cd "$NETWORK_DIR"
    
    # Генезис-блок для канала (Fabric 2.5+ без system channel)
    log_info "Создание генезис-блока для канала ${CHANNEL_NAME}..."
    configtxgen -profile DroneNetworkGenesis \
        -channelID $CHANNEL_NAME \
        -outputBlock ./channel-artifacts/${CHANNEL_NAME}.block
    
    if [ $? -ne 0 ]; then
        log_error "Ошибка при создании генезис-блока"
        exit 1
    fi
    
    # Также создаём genesis.block для совместимости
    cp ./channel-artifacts/${CHANNEL_NAME}.block ./channel-artifacts/genesis.block
    
    # Транзакция создания канала (для старых версий)
    log_info "Создание транзакции канала..."
    configtxgen -profile DroneChannel \
        -outputCreateChannelTx ./channel-artifacts/${CHANNEL_NAME}.tx \
        -channelID $CHANNEL_NAME 2>/dev/null || true
    
    # Anchor peers для каждой организации (ОБНОВЛЕНО - добавлены Orvd и Regulator)
    log_info "Создание anchor peer транзакций..."
    
    # Список всех организаций
    ALL_ORGS=("Aggregator" "Operator" "Insurer" "CertCenter" "Manufacturer" "Orvd" "Regulator")
    
    for ORG in "${ALL_ORGS[@]}"; do
        log_info "Генерация anchor peer для ${ORG}MSP..."
        configtxgen -profile DroneChannel \
            -outputAnchorPeersUpdate ./channel-artifacts/${ORG}MSPanchors.tx \
            -channelID $CHANNEL_NAME \
            -asOrg ${ORG}MSP
        
        if [ $? -ne 0 ]; then
            log_warn "Не удалось создать anchor peer для ${ORG}MSP"
        else
            log_success "Anchor peer для ${ORG}MSP создан"
        fi
    done
    
    log_success "Артефакты канала сгенерированы"
}

# Вывод информации о сгенерированных файлах
show_summary() {
    echo ""
    log_info "==================== СВОДКА ===================="
    echo ""
    log_info "Криптографические материалы:"
    if [ -d "$NETWORK_DIR/crypto-config" ]; then
        log_info "  - ordererOrganizations: созданы"
        log_info "  - peerOrganizations: созданы"
        log_info "    * Aggregator"
        log_info "    * Operator"
        log_info "    * Insurer"
        log_info "    * CertCenter"
        log_info "    * Manufacturer"
        log_info "    * Orvd (новая)"
        log_info "    * Regulator (новая)"
    else
        log_info "  Не найдены"
    fi
    echo ""
    log_info "Артефакты канала:"
    if [ -d "$NETWORK_DIR/channel-artifacts" ]; then
        ls -la "$NETWORK_DIR/channel-artifacts/" | grep -v total | sed 's/^/  /'
    else
        log_info "  Не найдены"
    fi
    echo ""
    log_info "================================================"
}

# Главная функция
main() {
    echo ""
    echo "=================================================="
    echo "  Drone Fleet - Hyperledger Fabric Network Setup"
    echo "=================================================="
    echo ""
    
    check_prerequisites
    clean
    generate_crypto
    generate_channel_artifacts
    show_summary
    
    echo ""
    log_success "Генерация завершена успешно!"
    log_info "Сгенерированы материалы для 7 организаций:"
    log_info "  - Aggregator, Operator, Insurer, CertCenter, Manufacturer"
    log_info "  - Orvd, Regulator"
    log_info ""
    log_info "Следующий шаг: ./scripts/network.sh up"
}

# Обработка аргументов
case "$1" in
    clean)
        clean
        ;;
    crypto)
        generate_crypto
        ;;
    channel)
        generate_channel_artifacts
        ;;
    *)
        main
        ;;
esac