#!/bin/bash

BRANCH=$1

echo "=== CI STARTED ==="
echo "Branch from webhook: $BRANCH"
echo "Pulling latest code INSIDE CI (for reference)..."
git fetch --all
git pull origin "$BRANCH"


echo "Ensuring network exists..."
docker network create ci-network || true

echo "Loading environment variables for Docker Compose..."
set -a
source ../weight/.env
source ../billing/.env
set +a

echo "Running TEST environment..."
# Get the absolute path to the devops directory and project root.
DEVOPS_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$DEVOPS_DIR/.." && pwd)"

# If running from inside CI container (/app_root), use host path
# Otherwise use the resolved path
if [[ "$PROJECT_ROOT" == "/app_root" ]]; then
    # We're in the CI container, need to use the actual host path
    # The CI container mounts /home/ubuntu/ganshmuel-purple to /app_root
    PROJECT_ROOT="/home/ubuntu/ganshmuel-purple"
fi

# Export PROJECT_ROOT for docker-compose to use in volume paths
export PROJECT_ROOT

# Change to devops directory for docker-compose path resolution
cd "$DEVOPS_DIR" || exit 1

docker compose -f docker-compose-test.yml down
docker compose -f docker-compose-test.yml up -d --build


################################################
# SELECT TESTS BASED ON BRANCH
###############################################
echo "Selecting test script..."

if [ "$BRANCH" = "weight" ]; then
    TEST_SCRIPTS=("../weight/e2e_test.py")

elif [ "$BRANCH" = "billing" ]; then
    TEST_SCRIPTS=("../billing/test_billing.sh")

elif [ "$BRANCH" = "main" ]; then
    TEST_SCRIPTS=(
        "../weight/e2e_test.py"
        "../billing/test_billing.sh"
    )

else
    echo "Unknown branch → Running ALL tests by default"
    TEST_SCRIPTS=(
        "../weight/e2e_test.py"
        "../billing/test_billing.sh"
    )
fi


################################################
# RUN TEST SCRIPTS
###############################################
for script in "${TEST_SCRIPTS[@]}"; do
    echo "-----------------------------------------"
    echo "Running test script: $script"
    echo "-----------------------------------------"

    # If Python
    if [[ "$script" == *.py ]]; then
        echo "→ Running Python test"
        if ! python3 "$script"; then
            echo "❌ Python test FAILED: $script"
            python3 -c "from email_service import send_build_status_email; send_build_status_email('Failure', '$BRANCH')"
            exit 1
        fi

    # If Bash
    elif [[ "$script" == *.sh ]]; then
        echo "→ Running Bash test"
        chmod +x "$script"   # רק ליתר ביטחון
        if ! bash "$script"; then
            echo "❌ Bash test FAILED: $script"
            python3 -c "from email_service import send_build_status_email; send_build_status_email('Failure', '$BRANCH')"
            exit 1
        fi

    else
        echo "❌ Unknown test type: $script"
        exit 1
    fi
done


echo "✅ All tests PASSED for branch: $BRANCH"


################################################
# DEPLOY (ONLY MAIN)
###############################################
if [ "$BRANCH" = "main" ]; then
    echo "Deploying to production..."
    docker compose -f docker-compose-prod.yml down
    docker compose -f docker-compose-prod.yml up -d --build
fi


###############################################
# SEND SUCCESS EMAIL
###############################################
python3 -c "from email_service import send_build_status_email; send_build_status_email('Success', '$BRANCH')"

echo "=== CI COMPLETED ==="
