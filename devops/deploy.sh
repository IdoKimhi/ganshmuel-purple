#!/bin/bash

BRANCH=$1
TARGET_BRANCH="feature/mailing"  # The branch you want to merge into
REPO_ROOT="/app_root" # As defined in docker-compose volumes

# Ensure we are in the devops directory
cd "$REPO_ROOT/devops" || exit 1

echo "=== CI STARTED ==="
echo "Branch: $BRANCH"

wait_for_service() {
    local service_name="$1"
    local port="$2"
    echo "⏳ Waiting for $service_name on $port to be healthy..."
    for i in {1..20}; do
        # Use service name (container-to-container)
        code=$(curl -s -o /dev/null -w "%{http_code}" "http://${service_name}:${port}/health" || echo "000")
        if [[ "$code" == "200" ]]; then
            echo "✅ $service_name is ready (HTTP 200)"
            return 0
        fi
        echo "Attempt $i: $code"
        sleep 2
    done
    echo "❌ $service_name did not become ready in time."
    return 1
}

wait_for_schema() {
    local service_name="$1"
    local port="$2"
    local endpoint="$3"
    echo "⏳ Waiting for $service_name schema via $endpoint..."
    for i in {1..30}; do # Increased attempts to 30 (60 seconds)
        # We need to successfully execute a DB-dependent query.
        code=$(curl -s -o /dev/null -w "%{http_code}" "http://${service_name}:${port}${endpoint}" || echo "000")
        if [[ "$code" == "200" ]]; then
            echo "✅ $service_name schema is ready (HTTP 200)"
            return 0
        fi
        echo "Attempt $i: $code"
        sleep 2
    done
    echo "❌ $service_name schema did not become ready in time."
    return 1
}

# 1. Setup Environment
echo "Loading environment variables..."
set -a
[ -f "../weight/.env" ] && source ../weight/.env
[ -f "../billing/.env" ] && source ../billing/.env
[ -f "recipient_config.env" ] && source recipient_config.env
set +a

# 2. Reset Test Environment
echo "Resetting Test Environment..."
docker compose -f docker-compose-test.yml down -v
docker compose -f docker-compose-test.yml up -d --build


# Wait for the Weight Service to be ready before testing
# if ! wait_for_service weight-app-test 5000; then
#     echo "Fatal: Weight service failed to start, aborting CI."
#     exit 1
# fi
if ! wait_for_schema weight-app-test 5000 "/unknown"; then
    echo "Fatal: Weight service schema is not ready, aborting CI."
    exit 1
fi


# 3. Define Test Logic
FAILED=0

# --- WEIGHT TESTS ---
echo "-----------------------------------------"
echo "Running Weight Tests (E2E)"
echo "-----------------------------------------"
if ! python3 ../weight/e2e_test.py; then
    echo "❌ Weight Tests FAILED"
    FAILED=1
    # Email DevOps AND Weight Team
    python3 email_service.py "Failure" "$BRANCH" "devops"
    python3 email_service.py "Failure" "$BRANCH" "weight"
else
    echo "✅ Weight Tests PASSED"
fi

# --- BILLING TESTS ---
echo "-----------------------------------------"
echo "Running Billing Tests"
echo "-----------------------------------------"
chmod +x ../billing/test_billing.sh
if ! bash ../billing/test_billing.sh; then
    echo "❌ Billing Tests FAILED"
    FAILED=1
    # Email DevOps AND Billing Team
    python3 email_service.py "Failure" "$BRANCH" "devops"
    python3 email_service.py "Failure" "$BRANCH" "billing"
else
    echo "✅ Billing Tests PASSED"
fi

# 4. Handle Final Outcome
echo "-----------------------------------------"
echo "Finalizing CI..."
echo "-----------------------------------------"

if [ $FAILED -eq 1 ]; then
    echo "❌ CI Pipeline Failed. Notifications sent."
    exit 1
else
    echo "✅ All tests PASSED."
    
    # 5. Create Pull Request
    echo "Attempting to create Pull Request ($BRANCH -> $TARGET_BRANCH)..."
    #if python3 create_pr.py "$BRANCH" "$TARGET_BRANCH"; then
    #    echo "✅ PR Creation triggered successfully."
    #else
    #    echo "⚠️ PR Creation encountered issues (check logs)."
    #fi

    # 6. Success Email (DevOps Only)
    python3 email_service.py "Success" "$BRANCH" "devops"

    # 7. Deploy (Only if main)
    if [ "$BRANCH" = "main" ]; then
        echo "Deploying to production..."
        docker compose -f docker-compose-prod.yml down
        docker compose -f docker-compose-prod.yml up -d --build
    fi
fi

echo "=== CI COMPLETED ==="