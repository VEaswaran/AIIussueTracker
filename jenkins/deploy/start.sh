#!/usr/bin/env bash
# =============================================================================
# deploy/start.sh — Remote start script executed by Jenkins Deploy stage
#
# Usage:  start.sh <full-path-to-jar>
#
# What it does:
#   1. Stops any running instance of the app (by PID file)
#   2. Starts the new JAR as a background process
#   3. Writes the new PID to ai-issue-tracker.pid
# =============================================================================
set -euo pipefail

JAR_PATH="${1:?Usage: start.sh <path-to-jar>}"
DEPLOY_DIR="$(dirname "$JAR_PATH")"
PID_FILE="${DEPLOY_DIR}/ai-issue-tracker.pid"
LOG_FILE="${DEPLOY_DIR}/ai-issue-tracker.log"

# --- Stop existing instance ---
if [[ -f "$PID_FILE" ]]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[deploy] Stopping existing process PID=$OLD_PID"
        kill "$OLD_PID"
        sleep 3
    fi
    rm -f "$PID_FILE"
fi

# --- Start new instance ---
echo "[deploy] Starting ${JAR_PATH}"
nohup java \
    -XX:+UseContainerSupport \
    -XX:MaxRAMPercentage=75.0 \
    -Djava.security.egd=file:/dev/./urandom \
    -Dmock.enabled=false \
    -jar "$JAR_PATH" \
    >> "$LOG_FILE" 2>&1 &

NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"
echo "[deploy] Started PID=$NEW_PID — logs at $LOG_FILE"

# --- Simple health check (wait up to 60s) ---
echo "[deploy] Waiting for app to become healthy..."
for i in $(seq 1 12); do
    sleep 5
    if curl -sf "http://localhost:8082/actuator/health" > /dev/null 2>&1; then
        echo "[deploy] ✅ App is healthy"
        exit 0
    fi
    echo "[deploy] ...attempt $i/12"
done

echo "[deploy] ⚠️  Health check did not pass within 60s — check $LOG_FILE"
exit 1

