#!/bin/bash

# Arguments passed from the Flask Webhook Handler
BRANCH=$1
PUSHER=$2
TEAM=$3

# --- Initial Setup and Validation ---
echo "=== CI STARTED ==="
echo "Branch from webhook: $BRANCH"
echo "Pusher: $PUSHER, Team: $TEAM"

# Guardrail: Script only runs for 'dev' branch in this pipeline
#if [ "$BRANCH" != "dev" ]; then
#    echo "🚨 ERROR: Deployment script only runs for 'dev' branch. Exiting."
#    exit 0
#fi

echo "Pulling latest code..."
git fetch --all
git pull origin "$BRANCH"

# Save the previous stable commit hash (HEAD^ assumed stable for simple rollback)
LATEST_STABLE_COMMIT=$(git rev-parse HEAD^)
CURRENT_COMMIT=$(git rev-parse HEAD)
echo "Current commit hash: $CURRENT_COMMIT"
echo "Latest stable commit for rollback: $LATEST_STABLE_COMMIT"

echo "Ensuring network exists..."
docker network create ci-network || true

echo "Loading environment variables for Docker Compose..."
set -a
source ../weight/.env
source ../billing/.env
set +a

echo "Running TEST environment..."
# Clean up and start test containers
docker compose -f docker-compose-test.yml down
docker compose -f docker-compose-test.yml up -d --build


###############################################
# TEST CONFIGURATION
###############################################
echo "Selecting test scripts..."
# Push to 'dev' runs all critical tests
TEST_SCRIPTS=(
    "../weight/e2e_test.py"
    "../billing/test_billing.sh"
)

# Array to track failed tests for the email body
FAILED_TESTS=()
OVERALL_STATUS="Success"


###############################################
# RUN TEST SCRIPTS
###############################################
for script in "${TEST_SCRIPTS[@]}"; do
    echo "-----------------------------------------"
    echo "Running test script: $script"
    echo "-----------------------------------------"

    SCRIPT_FAILED=0

    # If Python
    if [[ "$script" == *.py ]]; then
        if ! python3 "$script"; then
            SCRIPT_FAILED=1
        fi

    # If Bash
    elif [[ "$script" == *.sh ]]; then
        chmod +x "$script"
        if ! bash "$script"; then
            SCRIPT_FAILED=1
        fi

    else
        echo "❌ Unknown test type: $script"
        SCRIPT_FAILED=1
    fi
    
    # Handle result
    if [ "$SCRIPT_FAILED" -eq 1 ]; then
        echo "❌ Test FAILED: $script"
        FAILED_TESTS+=("$script")
        OVERALL_STATUS="Failure"
    fi
done


###############################################
# CI ACTION BASED ON OVERALL STATUS
###############################################

if [ "$OVERALL_STATUS" = "Failure" ]; then
    echo "❌ CI FAILED. Running failure actions..."

    # 1. Restore 'dev' branch to latest stable commit
    echo "Attempting to reset branch '$BRANCH' to stable commit: $LATEST_STABLE_COMMIT"
    #git reset --hard "$LATEST_STABLE_COMMIT" || {
    #    echo "CRITICAL WARNING: Rollback failed. Manual intervention required."
    #}
    
    # 2. Convert FAILED_TESTS array into a single comma-separated string for Python
    # This prevents quoting issues when passing arrays via the shell -c command.
    FAILURE_STRING=$(IFS=,; echo "${FAILED_TESTS[*]}")
    
    # 3. Send failure email
    # Arguments: STATUS BRANCH PUSHER TEAM FAILURE_STRING
    PYTHON_CMD="from email_service import send_ci_status_email_v2; send_ci_status_email_v2('Failure', '$BRANCH', '$PUSHER', '$TEAM', ['$FAILURE_STRING'])"
    
    python3 -c "$PYTHON_CMD"
    
    echo "=== CI COMPLETED WITH FAILURE ==="
    # Exit with code 1 so app.py knows the CI pipeline failed.
    exit 1 

else
    echo "✅ All tests PASSED for branch: $BRANCH"
    
    # 1. Simulate creation of Pull Request from dev to main
    echo "Simulating creation of Pull Request from $BRANCH to main..."
    
    # 2. Send success email
    PYTHON_CMD="from email_service import send_ci_status_email_v2; send_ci_status_email_v2('Success', '$BRANCH', '$PUSHER', '$TEAM')"
    python3 -c "$PYTHON_CMD"
    
    echo "=== CI COMPLETED WITH SUCCESS ==="
    # Exit with code 0 to signal success to app.py.
    exit 0 
fi
