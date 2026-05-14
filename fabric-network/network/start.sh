#!/bin/bash

# Главный скрипт запуска сети Hyperledger Fabric
# Drone Fleet Management System

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       Drone Fleet - Hyperledger Fabric Network              ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

show_help() {
    echo -e "${BLUE}Использование:${NC}"
    echo "  ./start.sh [команда]"
    echo ""
    echo -e "${BLUE}Команды:${NC}"
    echo "  install     Установить Fabric binaries и Docker images"
    echo "  up          Запустить всю инфраструктуру"
    echo "  down        Остановить сеть"
    echo "  restart     Перезапустить сеть"
    echo "  clean       Полная очистка"
    echo "  status      Статус сети"
    echo "  logs        Просмотр логов"
    echo ""
    echo -e "${BLUE}Пошаговый запуск:${NC}"
    echo "  generate    Генерация криптоматериалов"
    echo "  network     Запуск контейнеров"
    echo "  channel     Создание и настройка канала"
    echo "  deploy      Развертывание чейнкода"
    echo ""
    echo -e "${BLUE}Примеры:${NC}"
    echo "  ./start.sh install    # Установить зависимости"
    echo "  ./start.sh up         # Запустить всё"
    echo "  ./start.sh logs       # Посмотреть логи"
    echo ""
}

case "${1:-help}" in
    install)
        echo -e "${BLUE}[1/1]${NC} Установка Hyperledger Fabric..."
        ./scripts/install-fabric.sh all
        ;;
    
    up)
        echo -e "${BLUE}[1/4]${NC} Генерация криптоматериалов..."
        ./scripts/generate.sh
        
        echo ""
        echo -e "${BLUE}[2/4]${NC} Запуск сети..."
        ./scripts/network.sh up
        
        echo ""
        echo -e "${BLUE}[3/4]${NC} Настройка канала..."
        sleep 5
        ./scripts/channel.sh setup
        
        echo ""
        echo -e "${BLUE}[4/4]${NC} Развертывание чейнкода..."
        sleep 3
        ./scripts/chaincode.sh deploy
        
        echo ""
        echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║              [SUCCESS] Сеть успешно запущена!                ║${NC}"
        echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "${BLUE}Организации:${NC}"
        echo "  • Aggregator    - peer0.aggregator.drone-network.local:7051"
        echo "  • Operator      - peer0.operator.drone-network.local:8051"
        echo "  • Insurer       - peer0.insurer.drone-network.local:9051"
        echo "  • CertCenter    - peer0.certcenter.drone-network.local:10051"
        echo "  • Manufacturer  - peer0.manufacturer.drone-network.local:11051"
        echo ""
        echo -e "${BLUE}Канал:${NC} dronechannel"
        echo -e "${BLUE}Чейнкод:${NC} drone-chaincode"
        echo ""
        ;;
    
    down)
        ./scripts/network.sh down
        ;;
    
    restart)
        ./scripts/network.sh restart
        ;;
    
    clean)
        ./scripts/network.sh clean
        ;;
    
    status)
        ./scripts/network.sh status
        ;;
    
    logs)
        ./scripts/network.sh logs "${2:-}"
        ;;
    
    generate)
        ./scripts/generate.sh
        ;;
    
    network)
        ./scripts/network.sh "${2:-up}"
        ;;
    
    channel)
        ./scripts/channel.sh "${2:-setup}"
        ;;
    
    deploy)
        ./scripts/chaincode.sh deploy
        ;;
    
    test)
        ./scripts/chaincode.sh test
        ;;
    
    help|-h|--help)
        show_help
        ;;
    
    *)
        echo -e "${RED}Неизвестная команда: $1${NC}"
        show_help
        exit 1
        ;;
esac
