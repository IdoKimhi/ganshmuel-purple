#!/usr/bin/env bash
set -e

EMAIL_TO="moataz.ody44@gmail.com"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SEND_EMAIL="$SCRIPT_DIR/email_service.py"


send_alert() {
    local env="$1"
    local service="$2"
    local message="$3"

    python3 "$SEND_EMAIL" \
        monitor \
        "$service" \
        "$env" \
        "$message" \
        "$EMAIL_TO"
}


# ================================
# Detect running environment
# ================================
detect_env() {

    # אם יש קונטיינרים שמסתיימים ב -prod
    if docker ps --format '{{.Names}}' | grep -q "\-prod$"; then
        echo "prod"
        return
    fi

    # אם יש קונטיינרים שמסתיימים ב -test
    if docker ps --format '{{.Names}}' | grep -q "\-test$"; then
        echo "test"
        return
    fi

    echo "unknown"
}

ENVIRONMENT=$(detect_env)

if [[ "$ENVIRONMENT" == "prod" ]]; then
    echo "[MONITOR] ENV = PROD"

    DBS=("weight-db-prod" "billing-db-prod")
    APPS=("weight-app-prod" "billing-app-prod")

elif [[ "$ENVIRONMENT" == "test" ]]; then
    echo "[MONITOR] ENV = TEST"

    DBS=("weight-db-test" "billing-db-test")
    APPS=("weight-app-test" "billing-app-test")   # ← אם יש

else
    echo "[MONITOR] ERROR: Could not determine environment"
    exit 1
fi

# ================================
# 1) CHECK DATABASES
# ================================
for db in "${DBS[@]}"; do
    echo "[CHECK] DB: $db"

    if ! docker ps --format '{{.Names}}' | grep -q "$db"; then
        send_alert "$ENVIRONMENT" "$db" "Database container '$db' is DOWN."
        continue
    fi

    docker exec "$db" sh -c "mysqladmin ping -uroot -p\$MYSQL_ROOT_PASSWORD" >/dev/null 2>&1
    if [[ $? -ne 0 ]]; then
        send_alert "$ENVIRONMENT" "$db" "Cannot connect to MySQL inside '$db'."
    fi
done

# ================================
# 2) CHECK APPS
# ================================
for app in "${APPS[@]}"; do
    echo "[CHECK] APP: $app"

    if ! docker ps --format '{{.Names}}' | grep -q "$app"; then
        send_alert "$ENVIRONMENT" "$app" "App container '$app' is DOWN."
        continue
    fi

    APP_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$app")
    APP_PORT=5000

    curl -s "http://$APP_IP:$APP_PORT" >/dev/null 2>&1
    if [[ $? -ne 0 ]]; then
        send_alert "$ENVIRONMENT" "$app" "Flask app '$app' NOT responding."
    fi
done

echo "[MONITOR] Done."
exit 0
