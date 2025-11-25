#!/bin/bash

BRANCH=$1
PUSHER=${2:-\"ci_user\"}  # Default value if not provided
TEAM=${3:-\"devops\"}     # Default value if not provided

echo "=== CI STARTED ==="
echo "Branch from webhook: $BRANCH"
echo "Pusher: $PUSHER, Team: $TEAM"

# We are testing with the 'ido' branch locally, so we comment out the 'dev' check for now.
# if [ "$BRANCH" != "dev" ]; then
#     echo "🚨 ERROR: Deployment script only runs for 'dev' branch. Exiting."
#     exit 0
# fi

echo "Pulling latest code..."
git fetch --all
# NOTE: The pull should ideally be against the commit hash from the webhook, 
# but we stick to the branch for this example.
git pull origin "$BRANCH"

# Save the current commit hash for rollback later
LATEST_COMMIT=$(git rev-parse HEAD)
# Use a static placeholder for the last good commit for initial rollback test
STABLE_COMMIT="515e1b99c5e447b3bf02c0ef18c797fa6dfa645d"
echo "Current commit hash: $LATEST_COMMIT"
echo "Latest stable commit for rollback: $STABLE_COMMIT"


echo "Ensuring network exists..."
docker network create purple_network || true

echo "Loading environment variables for Docker Compose..."
set -a
# Assuming .env files are in the parent directory
source ../weight/.env
source ../billing/.env
set +a

# Start the test environment
echo "Running TEST environment..."
# Note: Use -f to specify the files for cleanup and startup
docker compose -f docker-compose-test.yml down -v --remove-orphans || true # Ensure clean start
docker compose -f docker-compose-test.yml up -d --build


# Array to track failed tests for the email body
FAILED_TESTS=()
OVERALL_STATUS="SUCCESS"


###############################################
# HEALTH CHECK WAIT LOOP (CRITICAL FIX)
###############################################
WEIGHT_APP_PORT=8086
BILLING_APP_PORT=8088
MAX_WAIT_SECONDS=60
START_TIME=$(date +%s)
HEALTHY=0

echo ""
echo "⏳ Waiting for microservices to be healthy (max $MAX_WAIT_SECONDS seconds)..."

while [ $(($(date +%s) - $START_TIME)) -lt $MAX_WAIT_SECONDS ]; do
    # Check Weight App Health Check (assuming a /health endpoint exists)
    WEIGHT_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$WEIGHT_APP_PORT/health || echo "000")
    
    # Check Billing App Health Check (assuming a /health endpoint exists)
    BILLING_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$BILLING_APP_PORT/health || echo "000")

    if [ "$WEIGHT_STATUS" == "200" ] && [ "$BILLING_STATUS" == "200" ]; then
        echo "✅ Both services reported healthy. Starting tests."
        HEALTHY=1
        break
    fi

    echo -n "."
    sleep 2
done

if [ "$HEALTHY" -eq 0 ]; then
    echo ""
    echo "❌ CRITICAL FAILURE: Microservices did not become healthy within $MAX_WAIT_SECONDS seconds."
    # We exit 1 here, triggering the failure flow below.
    FAILED_TESTS+=("CRITICAL: Services failed to start/become healthy")
    OVERALL_STATUS="FAILURE"
fi

###############################################
# SELECT TESTS BASED ON BRANCH (Simplified for 'ido' test branch)
###############################################
if [ "$OVERALL_STATUS" == "SUCCESS" ]; then
    echo "Selecting test scripts..."
    # When pushing to 'ido', run all tests by default
    TEST_SCRIPTS=(\
        "../weight/e2e_test.py"\
        "../billing/test_billing.sh"\
    )


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
                FAILED_TESTS+=("$script")
                OVERALL_STATUS="FAILURE"
            fi

        # If Bash
        elif [[ "$script" == *.sh ]]; then
            echo "→ Running Bash test"
            chmod +x "$script"   # Ensure executable
            if ! bash "$script"; then
                echo "❌ Bash test FAILED: $script"
                FAILED_TESTS+=("$script")
                OVERALL_STATUS="FAILURE"
            fi

        else
            echo "❌ Unknown test type: $script"
            FAILED_TESTS+=("Unknown test type: $script")
            OVERALL_STATUS="FAILURE"
        fi
    done
fi


###############################################
# CLEANUP (Always run)
###############################################
echo ""
echo "🧹 Cleaning up test environment..."
docker compose -f docker-compose-test.yml down -v --remove-orphans || true


###############################################
# FINAL STATUS CHECK & EMAIL
###############################################
if [ "$OVERALL_STATUS" == "FAILURE" ]; then
    echo "❌ CI FAILED. Running failure actions..."
    
    # 1. Rollback
    echo "Attempting to reset branch '$BRANCH' to stable commit: $STABLE_COMMIT"
    #git reset --hard "$STABLE_COMMIT" || {
    #    echo "WARNING: Could not reset to $STABLE_COMMIT. Manual check required."
    #}
    
    # 2. Build Python arguments string (FIXED SYNTAX ERROR HERE)
    # Start with mandatory arguments
    PYTHON_ARGS="'Failure', '$BRANCH', '$PUSHER', '$TEAM'"
    
    # Append failure details, quoted correctly
    for failure in "${FAILED_TESTS[@]}"; do
        # Appends the failure item as a quoted string argument
        PYTHON_ARGS="${PYTHON_ARGS}, '$failure'"
    done
    
    # Send failure email 
    # Use the constructed string to call the function
    python3 -c "from email_service import send_ci_status_email_v2; send_ci_status_email_v2($PYTHON_ARGS)"\
        || echo "WARNING: Email sending failed. Check email_service.py."

    echo "=== CI COMPLETED WITH FAILURE ==="
    exit 1

else
    echo "✅ All tests PASSED for branch: $BRANCH"
    
    # 1. Simulating Pull Request
    echo "Simulating creation of Pull Request from $BRANCH to main..."
    
    # 2. Send success email
    python3 -c "from email_service import send_ci_status_email_v2; send_ci_status_email_v2('Success', '$BRANCH', '$PUSHER', '$TEAM')"\
        || echo "WARNING: Email sending failed. Check email_service.py."
    
    echo "=== CI COMPLETED WITH SUCCESS ==="
    exit 0
fi