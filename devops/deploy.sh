#!/bin/bash

BRANCH=$1

echo "=== CI STARTED ==="
echo "Branch from webhook: $BRANCH"

echo "Pulling latest code..."
git fetch --all
git pull origin "$BRANCH"

echo "Ensuring network exists..."
docker network create ci-network || true

echo "Running TEST environment..."
docker compose -f docker-compose.test.yml down
docker compose -f docker-compose.test.yml up -d --build


###############################################
# SELECT TESTS BASED ON BRANCH
###############################################
echo "Selecting test script..."

if [ "$BRANCH" = "weight" ]; then
    TEST_SCRIPTS=("../weight/verify_weight_api.py")

elif [ "$BRANCH" = "billing" ]; then
    TEST_SCRIPTS=("../billing/test_billing.sh")
elif [ "$BRANCH" ="dev"]; then
    TEST_SCRIPTS=(
        "../weight/verify_weight_api.py"
        "../billing/test_billing.sh"
        # "tests/e2e_test_flow.py"
    )

elif [ "$BRANCH" = "main" ]; then
    TEST_SCRIPTS=(
        "../weight/verify_weight_api.py"
        "../billing/test_billing.sh"
        # "tests/e2e_test_flow.py"

    )

else
    echo "Unknown branch → Running ALL tests by default"
    TEST_SCRIPTS=(
        "../weight/verify_weight_api.py"
        "../billing/test_billing.sh"
        # "tests/e2e_test_flow.py"

    )
fi


###############################################
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


###############################################
# DEPLOY (ONLY MAIN)
###############################################
if [ "$BRANCH" = "main" ]; then
    echo "Deploying to production..."
    docker compose -f docker-compose.prod.yml down
    docker compose -f docker-compose.prod.yml up -d --build
fi


###############################################
# SEND SUCCESS EMAIL
###############################################
python3 -c "from email_service import send_build_status_email; send_build_status_email('Success', '$BRANCH')"

echo "=== CI COMPLETED ==="
