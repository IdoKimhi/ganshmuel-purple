#!/bin/bash

BRANCH=$1
TARGET_BRANCH="feature/mailing"  # The branch you want to merge into
REPO_ROOT="/app_root" # As defined in docker-compose volumes

# Ensure we are in the devops directory
cd "$REPO_ROOT/devops" || exit 1

echo "=== CI STARTED ==="
echo "Branch: $BRANCH"

# 1. Setup Environment
echo "Loading environment variables..."
set -a
[ -f "../weight/.env" ] && source ../weight/.env
[ -f "../billing/.env" ] && source ../billing/.env
[ -f "recipient_config.env" ] && source recipient_config.env
set +a

# 2. Reset Test Environment
echo "Resetting Test Environment..."
docker compose -f docker-compose-test.yml down
docker compose -f docker-compose-test.yml up -d --build

#this is dumb
sleep 25

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