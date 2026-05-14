#!/usr/bin/env bash
# Триггерит Jenkins job и (опционально) ждёт завершения.
# Usage: ./build.sh <job-name> [--wait]

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE not found. Run 'make jenkins-up' first or copy .env.example -> .env" >&2
    exit 1
fi

set -a
. "$ENV_FILE"
set +a

JOB="${1:?Usage: $0 <job-name> [--wait]}"
WAIT="${2:-}"
HOST="http://localhost:${JENKINS_HTTP_PORT:-8080}"
AUTH="${JENKINS_ADMIN_USER}:${JENKINS_ADMIN_PASSWORD}"

COOKIE_JAR=$(mktemp)
trap 'rm -f "$COOKIE_JAR"' EXIT

echo ">>> Fetching CSRF crumb"
CRUMB_JSON=$(curl -fSs -u "$AUTH" -c "$COOKIE_JAR" -b "$COOKIE_JAR" "$HOST/crumbIssuer/api/json" || true)
CRUMB_FIELD=$(echo "$CRUMB_JSON" | sed -n 's/.*"crumbRequestField":"\([^"]*\)".*/\1/p')
CRUMB_VALUE=$(echo "$CRUMB_JSON" | sed -n 's/.*"crumb":"\([^"]*\)".*/\1/p')

echo ">>> Triggering build: $HOST/job/$JOB/build"
QUEUE_URL=$(curl -fSs -u "$AUTH" -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
    ${CRUMB_FIELD:+-H "${CRUMB_FIELD}: ${CRUMB_VALUE}"} \
    -X POST -D - "$HOST/job/$JOB/build" \
    | awk -F': ' 'tolower($1)=="location" {print $2}' | tr -d '\r\n')

if [ -z "$QUEUE_URL" ]; then
    echo "Triggered (no queue location returned)."
    exit 0
fi

echo ">>> Queued: $QUEUE_URL"

if [ "$WAIT" != "--wait" ]; then
    exit 0
fi

echo ">>> Waiting for build to start..."
for _ in $(seq 1 60); do
    BUILD_URL=$(curl -fSs -u "$AUTH" "${QUEUE_URL}api/json" \
        | python3 -c 'import sys,json; d=json.load(sys.stdin); print((d.get("executable") or {}).get("url",""))' \
        || true)
    if [ -n "$BUILD_URL" ] && [ "$BUILD_URL" != "null" ]; then break; fi
    sleep 2
done

if [ -z "$BUILD_URL" ]; then
    echo "Build did not start within timeout." >&2
    exit 1
fi

echo ">>> Build started: $BUILD_URL"
echo ">>> Streaming console (progressive)..."
START=0
while :; do
    HEADERS=$(mktemp)
    curl -fSs -u "$AUTH" -D "$HEADERS" "${BUILD_URL}logText/progressiveText?start=${START}" || true
    NEXT=$(awk -F': ' 'tolower($1)=="x-text-size" {print $2}' "$HEADERS" | tr -d '\r\n')
    MORE=$(awk -F': ' 'tolower($1)=="x-more-data" {print $2}' "$HEADERS" | tr -d '\r\n')
    rm -f "$HEADERS"
    if [ -n "$NEXT" ]; then START="$NEXT"; fi
    if [ "$MORE" != "true" ]; then break; fi
    sleep 2
done

RESULT=$(curl -fSs -u "$AUTH" "${BUILD_URL}api/json" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin).get("result") or "")')
echo ">>> Build result: ${RESULT:-UNKNOWN}"
[ "$RESULT" = "SUCCESS" ]
