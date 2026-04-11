# Точка входа интеграции: НУС/Дронопорт/SITL — DronePortGCS-integration_drone; дрон — Agrodron-master/agrodron.

NUS_DIR := DronePortGCS-integration_drone
AGRODRON_DIR := Agrodron/agrodron

.PHONY: help stack-up stack-down docker-net web-nus agrodron-up agrodron-down full-stack-up full-stack-down

help:
	@echo "Интеграция (корень Integ):"
	@echo "  make stack-up       — брокер + НУС + Дронопорт + SITL (дрон НЕ входит в эту команду)"
	@echo "  make agrodron-up    — контейнеры Агродрона к уже запущенному mosquitto (после stack-up)"
	@echo "  make full-stack-up  — stack-up, затем agrodron-up"
	@echo "  make agrodron-down  — остановить только сервисы Агродрона"
	@echo "  make stack-down     — остановить НУС/Дронопорт/SITL/брокер"
	@echo "  make full-stack-down — agrodron-down + stack-down"
	@echo "  make docker-net     — создать внешнюю сеть drones_net (если ещё нет)"
	@echo "  make web-nus        — веб НУС после stack-up (порт 8000)"
	@echo "НУС: $(NUS_DIR)  |  Дрон: $(AGRODRON_DIR)"

stack-up:
	@$(MAKE) -C $(NUS_DIR) stack-with-sitl-up

stack-down:
	@$(MAKE) -C $(NUS_DIR) stack-with-sitl-down

docker-net:
	@$(MAKE) -C $(NUS_DIR) docker-net

web-nus:
	@$(MAKE) -C $(NUS_DIR) web-nus

agrodron-up:
	@echo "[agrodron] Нужны сеть drones_net и брокер mosquitto (сначала: make stack-up или make docker-net)"
	@$(MAKE) -C $(AGRODRON_DIR) docker-up-components

agrodron-down:
	@$(MAKE) -C $(AGRODRON_DIR) docker-down

full-stack-up: stack-up agrodron-up

full-stack-down: agrodron-down stack-down
