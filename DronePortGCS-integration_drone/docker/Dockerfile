# Dockerfile for drones_v2 systems
# Usage: docker build -t drones_v2-system -f docker/Dockerfile .
#        docker run -e SYSTEM_TYPE=dummy -e SYSTEM_ID=dummy_001 drones_v2-system

FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY config/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set Python path
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default environment variables
ENV SYSTEM_TYPE=dummy
ENV BROKER_TYPE=kafka
ENV KAFKA_BOOTSTRAP_SERVERS=kafka:9092

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${HEALTH_PORT:-9700}/health || exit 1

# Default command - unified entry point (python -m systems)
CMD ["python", "-m", "systems"]
