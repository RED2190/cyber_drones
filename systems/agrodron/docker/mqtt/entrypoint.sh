#!/bin/sh
set -e

ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin123}"

rm -f /mosquitto/data/passwd /mosquitto/data/acl

# Создаём admin
mosquitto_passwd -b -c /mosquitto/data/passwd "$ADMIN_USER" "$ADMIN_PASSWORD"
printf "user %s\ntopic readwrite #\n" "$ADMIN_USER" > /mosquitto/data/acl

# Автоматически добавляем всех COMPONENT_USER_* из env
env | grep '^COMPONENT_USER_' | sort | while IFS='=' read -r VAR USERNAME; do
  [ -z "$USERNAME" ] && continue
  SUFFIX="${VAR#COMPONENT_USER_}"
  PASSWORD_VAR="COMPONENT_PASSWORD_${SUFFIX}"
  PASSWORD=$(eval echo "\$$PASSWORD_VAR")
  mosquitto_passwd -b /mosquitto/data/passwd "$USERNAME" "$PASSWORD"
  printf "\nuser %s\ntopic readwrite #\n" "$USERNAME" >> /mosquitto/data/acl
done

chown mosquitto:mosquitto /mosquitto/data/passwd /mosquitto/data/acl
chmod 700 /mosquitto/data/acl

exec mosquitto -c /mosquitto/config/mosquitto.conf
