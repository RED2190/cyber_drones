#!/bin/bash

# Скрипт управления сетью Hyperledger Fabric
# Drone Fleet Management System

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK_DIR="$(dirname "$SCRIPT_DIR")"
CHANNEL_NAME="dronechannel"
COMPOSE_FILE="$NETWORK_DIR/docker-compose.yaml"

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

# Проверка Docker
check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker не установлен"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker daemon не запущен"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose не установлен"
        exit 1
    fi
}

# Функция для docker-compose (поддержка v1 и v2)
docker_compose() {
    if docker compose version &> /dev/null; then
        docker compose "$@"
    else
        docker-compose "$@"
    fi
}

# Запуск сети
network_up() {
    log_info "Запуск сети Hyperledger Fabric..."
    
    # Проверяем наличие криптоматериалов
    if [ ! -d "$NETWORK_DIR/crypto-config" ]; then
        log_error "Криптографические материалы не найдены!"
        log_info "Сначала выполните: ./scripts/generate.sh"
        exit 1
    fi
    
    cd "$NETWORK_DIR"
    
    # Запуск контейнеров
    docker_compose -f "$COMPOSE_FILE" up -d
    
    # Ждем запуска
    log_info "Ожидание запуска контейнеров..."
    sleep 10
    
    # Проверяем статус
    docker_compose -f "$COMPOSE_FILE" ps
    
    log_success "Сеть запущена!"
    echo ""
    log_info "Запущены следующие организации:"
    log_info "  - Aggregator (агрегатор)"
    log_info "  - Operator (оператор)"
    log_info "  - Insurer (страховая)"
    log_info "  - CertCenter (сертификационный центр)"
    log_info "  - Manufacturer (производитель)"
    log_info "  - Orvd (ОрВД - новая организация)"
    log_info "  - Regulator (регулятор - новая организация)"
    echo ""
    log_info "Следующие шаги:"
    log_info "  1. Создайте канал: ./scripts/channel.sh create"
    log_info "  2. Присоедините пиры: ./scripts/channel.sh join"
    log_info "  3. Разверните чейнкод: ./scripts/chaincode.sh deploy"
}

# Остановка сети
network_down() {
    log_info "Остановка сети..."
    
    cd "$NETWORK_DIR"
    
    docker_compose -f "$COMPOSE_FILE" down --volumes --remove-orphans
    
    # Удаление контейнеров чейнкода
    docker rm -f $(docker ps -aq --filter "name=dev-peer*") 2>/dev/null || true
    
    # Удаление образов чейнкода
    docker rmi -f $(docker images -q --filter "reference=dev-peer*") 2>/dev/null || true
    
    log_success "Сеть остановлена"
}

# Перезапуск сети
network_restart() {
    network_down
    sleep 2
    network_up
}

# Статус сети
network_status() {
    log_info "Статус контейнеров сети (все 7 организаций):"
    echo ""
    
    cd "$NETWORK_DIR"
    docker_compose -f "$COMPOSE_FILE" ps
    
    echo ""
    log_info "Проверка запущенных пиров:"
    echo ""
    
    # Проверяем статус каждого пира
    local peers=(
        "orderer.drone-network.local"
        "peer0.aggregator.drone-network.local"
        "peer0.operator.drone-network.local"
        "peer0.insurer.drone-network.local"
        "peer0.certcenter.drone-network.local"
        "peer0.manufacturer.drone-network.local"
        "peer0.orvd.drone-network.local"
        "peer0.regulator.drone-network.local"
        "cli"
    )
    
    for peer in "${peers[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "^$peer$"; then
            status=$(docker inspect --format='{{.State.Status}}' "$peer" 2>/dev/null)
            if [ "$status" == "running" ]; then
                echo -e "  ${GREEN}✓${NC} $peer - запущен"
            else
                echo -e "  ${YELLOW}⚠${NC} $peer - $status"
            fi
        else
            echo -e "  ${RED}✗${NC} $peer - не найден"
        fi
    done
    
    echo ""
    log_info "Логи можно просмотреть командой:"
    log_info "  docker logs <container_name>"
}

# Просмотр логов
network_logs() {
    local container=$1
    
    cd "$NETWORK_DIR"
    
    if [ -z "$container" ]; then
        docker_compose -f "$COMPOSE_FILE" logs -f
    else
        docker_compose -f "$COMPOSE_FILE" logs -f "$container"
    fi
}

# Полная очистка
network_clean() {
    log_warn "Полная очистка сети и всех артефактов..."
    
    network_down 2>/dev/null || true
    
    cd "$NETWORK_DIR"
    rm -rf crypto-config
    rm -rf channel-artifacts
    
    # Очистка Docker volumes
    docker volume prune -f
    
    log_success "Очистка завершена"
}

# Показать помощь
show_help() {
    echo ""
    echo "=================================================="
    echo "  Drone Fleet - Hyperledger Fabric Network"
    echo "=================================================="
    echo ""
    echo "Управление сетью Hyperledger Fabric"
    echo ""
    echo "Организации в сети (7 организаций):"
    echo "  - Aggregator  (агрегатор)        - порт 7051"
    echo "  - Operator    (оператор)         - порт 8051"
    echo "  - Insurer     (страховая)        - порт 9051"
    echo "  - CertCenter  (серт. центр)      - порт 10051"
    echo "  - Manufacturer (производитель)   - порт 11051"
    echo "  - Orvd        (ОрВД)             - порт 12051"
    echo "  - Regulator   (регулятор)        - порт 13051"
    echo ""
    echo "Использование: $0 <команда> [опции]"
    echo ""
    echo "Команды:"
    echo "  up          Запустить сеть"
    echo "  down        Остановить сеть"
    echo "  restart     Перезапустить сеть"
    echo "  status      Показать статус контейнеров"
    echo "  logs [name] Показать логи (опционально: имя контейнера)"
    echo "  clean       Полная очистка (остановка + удаление артефактов)"
    echo ""
    echo "Примеры:"
    echo "  $0 up"
    echo "  $0 status"
    echo "  $0 logs orderer.drone-network.local"
    echo "  $0 logs peer0.orvd.drone-network.local"
    echo "  $0 down"
    echo ""
}

# Главная логика
main() {
    check_docker
    
    case "$1" in
        up)
            network_up
            ;;
        down)
            network_down
            ;;
        restart)
            network_restart
            ;;
        status)
            network_status
            ;;
        logs)
            network_logs "$2"
            ;;
        clean)
            network_clean
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
}

if [ $# -lt 1 ]; then
    show_help
    exit 1
fi

main "$@"