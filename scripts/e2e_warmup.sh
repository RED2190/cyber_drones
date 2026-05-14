#!/usr/bin/env bash
# Стабилизатор E2E-стенда после "up".
#
# 1. Пре-создаём критичные для Agregator Kafka-топики.
#    segmentio/kafka-go v0.4.47 при JoinGroup получает partition-assignment
#    из метаданных, и если топика в метаданных ещё нет (его создаст только
#    первый producer), он навсегда остаётся с empty assignment и не пере-
#    подписывается, даже когда топик появляется. Поэтому создаём топики
#    заранее — до старта агрегатора и консюмеров.
#
# 2. Перезапускаем Agregator: на случай, если он успел присоединиться к
#    группе до того, как топик был создан, и сидит с empty assignment.
#
# NB: это страховка уровня инфраструктуры под баг kafka-go v0.4.47.
# Правильное решение — пусть Agregator на старте сам создаёт свои
# топики через AdminClient (или обновит kafka-go). До этого момента
# список топиков здесь захардкожен и должен совпадать с дефолтами из
# systems/Agregator/internal/config/config.go.
#
# Переменные окружения:
#   ADMIN_USER / ADMIN_PASSWORD — SASL-учётка брокера (берутся из docker/.env).

set -euo pipefail

ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin_secret_123}"

KAFKA_CONTAINER="${KAFKA_CONTAINER:-kafka}"
AGREGATOR_CONTAINER_PATTERN="${AGREGATOR_CONTAINER_PATTERN:-aggregator}"

echo "=== Ensuring Kafka topics for Agregator (race-fix) ==="

if ! docker ps --format '{{.Names}}' | grep -qx "${KAFKA_CONTAINER}"; then
  echo "WARNING: kafka container '${KAFKA_CONTAINER}' is not running; skipping topic init"
  exit 0
fi

docker exec -i -e ADMIN_USER="${ADMIN_USER}" -e ADMIN_PASSWORD="${ADMIN_PASSWORD}" \
  "${KAFKA_CONTAINER}" sh -s <<'BROKER_SH'
set -e
cat > /tmp/admin-client.properties <<EOF
security.protocol=SASL_PLAINTEXT
sasl.mechanism=PLAIN
sasl.jaas.config=org.apache.kafka.common.security.plain.PlainLoginModule required username="${ADMIN_USER}" password="${ADMIN_PASSWORD}";
EOF
for t in \
  systems.agregator \
  components.agregator.responses \
  components.agregator.operator.requests \
  components.agregator.operator.responses \
  errors.dead_letters \
  components.Agrodron.security_monitor \
  components.Agrodron.autopilot \
  components.Agrodron.mission_handler \
  components.Agrodron.navigation \
  components.Agrodron.telemetry \
  components.Agrodron.motors \
  components.Agrodron.sprayer \
  components.Agrodron.journal \
  components.Agrodron.limiter \
  components.Agrodron.emergensy \
  components.Agrodron.system_monitor \
  gcs.components.drone_manager \
  gcs.components.orchestrator \
  gcs.components.mission_converter \
  gcs.components.path_planner \
  gcs.components.mission_store \
  gcs.components.drone_store \
  drone_port.components.drone_registry \
  drone_port.components.drone_manager \
  drone_port.components.port_manager \
  drone_port.components.charging_manager \
  drone_port.components.state_store \
  drone_port.components.orchestrator \
  systems.orvd_system \
  components.orvd_component \
  systems.regulator \
  components.regulator \
  systems.insurer \
  components.insurer_service \
  systems.operator \
  components.operator \
  sitl.telemetry.request \
  sitl.telemetry.response \
  sitl.commands \
  sitl.verified-commands \
  sitl.verified-home \
  sitl-drone-home
do
  /opt/kafka/bin/kafka-topics.sh \
    --bootstrap-server localhost:29092 \
    --command-config /tmp/admin-client.properties \
    --create --if-not-exists \
    --topic "$t" --partitions 1 --replication-factor 1 \
    >/dev/null
  echo "  ensured topic: $t"
done
BROKER_SH

echo "=== Restarting Agregator to re-join consumer groups with valid metadata ==="
agregator_ids=$(docker ps --format '{{.Names}}' | grep -i "${AGREGATOR_CONTAINER_PATTERN}" || true)
if [ -n "${agregator_ids}" ]; then
  echo "${agregator_ids}" | xargs -r docker restart >/dev/null
  echo "  restarted: ${agregator_ids}"
else
  echo "  no Agregator containers found (pattern: ${AGREGATOR_CONTAINER_PATTERN})"
fi

echo "=== Warmup sanity done ==="
