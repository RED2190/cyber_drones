#!/bin/bash
set -e

echo "========================================"
echo "ENTRYPOINT SCRIPT STARTED"
echo "HOSTNAME: $HOSTNAME"

# Получаем номер из hostname (например, из "9dc68eeab9a8" не получится, но для insurance-service-1 получится)
if [ -z "$INSTANCE_ID" ]; then
    echo "INSTANCE_ID not set, trying to extract from HOSTNAME..."

    # Пробуем извлечь номер из hostname (для формата имя-число)
    INSTANCE_ID=$(echo $HOSTNAME | grep -o '[0-9]*$' | head -1)

    # Если не получилось (как в вашем случае с хэшем), используем последние 4 символа
    if [ -z "$INSTANCE_ID" ]; then
        INSTANCE_ID=$(echo $HOSTNAME | tail -c 5)
        echo "Using last 4 chars of HOSTNAME: $INSTANCE_ID"
    fi

    # Если всё ещё пусто, генерируем случайное число
    if [ -z "$INSTANCE_ID" ]; then
        INSTANCE_ID=$RANDOM
        echo "Generated random INSTANCE_ID: $INSTANCE_ID"
    fi
fi

echo "Final INSTANCE_ID: $INSTANCE_ID"
echo "========================================"

# Экспортируем переменную для Java
export INSTANCE_ID

# Запускаем приложение
echo "Starting Java application..."
exec java -jar /app/app.jar