#!/bin/bash

# Скрипт установки Hyperledger Fabric binaries и Docker images
# Drone Fleet Management System

set -e

FABRIC_VERSION="2.5.4"
CA_VERSION="1.5.7"

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
    log_info "Проверка Docker..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker не установлен!"
        log_info "Установите Docker: https://docs.docker.com/engine/install/"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker daemon не запущен!"
        log_info "Запустите Docker: sudo systemctl start docker"
        exit 1
    fi
    
    log_success "Docker установлен и работает"
}

# Проверка Go
check_go() {
    log_info "Проверка Go..."
    
    if ! command -v go &> /dev/null; then
        log_warn "Go не установлен. Для сборки чейнкода потребуется Go 1.21+"
        log_info "Установите Go: https://golang.org/dl/"
    else
        local go_version=$(go version | awk '{print $3}' | sed 's/go//')
        log_success "Go установлен: $go_version"
    fi
}

# Проверка jq
check_jq() {
    log_info "Проверка jq..."
    
    if ! command -v jq &> /dev/null; then
        log_warn "jq не установлен. Устанавливаем..."
        if command -v apt-get &> /dev/null; then
            sudo apt-get update && sudo apt-get install -y jq
        elif command -v pacman &> /dev/null; then
            sudo pacman -S --noconfirm jq
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y jq
        else
            log_error "Не удалось установить jq. Установите вручную."
        fi
    fi
    
    log_success "jq установлен"
}

# Скачивание Fabric binaries
download_fabric_binaries() {
    log_info "Скачивание Hyperledger Fabric binaries v${FABRIC_VERSION}..."
    
    local INSTALL_DIR="$HOME/fabric"
    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    
    # Скачиваем официальный скрипт установки
    curl -sSL https://bit.ly/2ysbOFE | bash -s -- ${FABRIC_VERSION} ${CA_VERSION} -s
    
    log_success "Fabric binaries скачаны в $INSTALL_DIR"
    
    # Добавляем в PATH
    local FABRIC_BIN="$INSTALL_DIR/fabric-samples/bin"
    
    if [[ ":$PATH:" != *":$FABRIC_BIN:"* ]]; then
        log_info "Добавление Fabric bin в PATH..."
        
        # Определяем shell config файл
        local SHELL_RC=""
        if [ -f "$HOME/.bashrc" ]; then
            SHELL_RC="$HOME/.bashrc"
        elif [ -f "$HOME/.zshrc" ]; then
            SHELL_RC="$HOME/.zshrc"
        fi
        
        if [ -n "$SHELL_RC" ]; then
            echo "" >> "$SHELL_RC"
            echo "# Hyperledger Fabric" >> "$SHELL_RC"
            echo "export PATH=\$PATH:$FABRIC_BIN" >> "$SHELL_RC"
            log_success "PATH обновлен в $SHELL_RC"
            log_warn "Выполните: source $SHELL_RC"
        fi
        
        # Экспортируем для текущей сессии
        export PATH=$PATH:$FABRIC_BIN
    fi
}

# Загрузка Docker images
pull_docker_images() {
    log_info "Загрузка Docker images для Hyperledger Fabric..."
    
    local images=(
        "hyperledger/fabric-peer:${FABRIC_VERSION}"
        "hyperledger/fabric-orderer:${FABRIC_VERSION}"
        "hyperledger/fabric-tools:${FABRIC_VERSION}"
        "hyperledger/fabric-ccenv:${FABRIC_VERSION}"
        "hyperledger/fabric-baseos:${FABRIC_VERSION}"
        "hyperledger/fabric-ca:${CA_VERSION}"
    )
    
    for image in "${images[@]}"; do
        log_info "Загрузка $image..."
        docker pull "$image"
    done
    
    # Тегируем как latest
    docker tag hyperledger/fabric-peer:${FABRIC_VERSION} hyperledger/fabric-peer:2.5
    docker tag hyperledger/fabric-orderer:${FABRIC_VERSION} hyperledger/fabric-orderer:2.5
    docker tag hyperledger/fabric-tools:${FABRIC_VERSION} hyperledger/fabric-tools:2.5
    
    log_success "Docker images загружены"
}

# Проверка установки
verify_installation() {
    log_info "Проверка установки..."
    
    echo ""
    log_info "Fabric binaries:"
    
    for cmd in cryptogen configtxgen peer; do
        if command -v $cmd &> /dev/null; then
            echo "  [OK] $cmd: $(which $cmd)"
        else
            echo "  [FAIL] $cmd: не найден"
        fi
    done
    
    echo ""
    log_info "Docker images:"
    docker images | grep hyperledger | head -10
}

# Показать помощь
show_help() {
    echo ""
    echo "Установка Hyperledger Fabric"
    echo ""
    echo "Использование: $0 [команда]"
    echo ""
    echo "Команды:"
    echo "  all       Полная установка (по умолчанию)"
    echo "  binaries  Только binaries"
    echo "  images    Только Docker images"
    echo "  verify    Проверить установку"
    echo ""
}

# Полная установка
install_all() {
    echo ""
    echo "=================================================="
    echo "  Установка Hyperledger Fabric"
    echo "  Version: ${FABRIC_VERSION}"
    echo "=================================================="
    echo ""
    
    check_docker
    check_go
    check_jq
    
    download_fabric_binaries
    pull_docker_images
    
    verify_installation
    
    echo ""
    log_success "Установка завершена!"
    echo ""
    log_info "Следующие шаги:"
    log_info "  1. source ~/.bashrc (или ~/.zshrc)"
    log_info "  2. cd network && ./scripts/generate.sh"
    log_info "  3. ./scripts/network.sh up"
}

# Главная логика
case "${1:-all}" in
    all)
        install_all
        ;;
    binaries)
        check_docker
        download_fabric_binaries
        ;;
    images)
        check_docker
        pull_docker_images
        ;;
    verify)
        verify_installation
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
