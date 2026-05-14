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

CMD ["python", "-m", "systems.agrodron.src.mission_handler"]

