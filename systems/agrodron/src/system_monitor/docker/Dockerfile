FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY config/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sdk/ /app/sdk/
COPY broker/ /app/broker/
COPY systems/agrodron/ /app/systems/agrodron/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Порт должен совпадать с SYSTEM_MONITOR_HTTP_PORT (по умолчанию 8090)
EXPOSE 8090

CMD ["python", "-m", "systems.agrodron.src.system_monitor"]
