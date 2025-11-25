#!/bin/bash

BRANCH=$1
PUSHER=${2:-\"ci_user\"}  # Default value if not provided
TEAM=${3:-\"devops\"}     # Default value if not provided

echo "=== CI STARTED ==="
echo "Branch from webhook: $BRANCH"
echo "Pusher: $PUSHER, Team: $TEAM"

# --- REMOVED: Initial branch check is now done in app.py ---
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
echo "Latest commit hash for rollback: $LATEST_COMMIT"

echo "Ensuring network exists..."
docker network create ci-network || true

echo "Loading environment variables for Docker Compose..."
set -a
source ../weight/.env
source ../billing/.env
set +a

echo "Running TEST environment..."
docker compose -f docker-compose-test.yml down
docker compose -f docker-compose-test.yml up -d --build


###############################################
# SELECT TESTS BASED ON BRANCH (Simplified for 'dev')
###############################################
echo "Selecting test scripts..."
# When pushing to 'dev', we assume all core tests should run
TEST_SCRIPTS=(
    "../weight/e2e_test.py"
    "../billing/test_billing.sh"
)

# Array to track failed tests for the email body
FAILED_TESTS=()
OVERALL_STATUS=0 # 0 for success, 1 for failure

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
            OVERALL_STATUS=1
        fi

    # If Bash
    elif [[ "$script" == *.sh ]]; then
        echo "→ Running Bash test"
        chmod +x "$script"   # רק ליתר ביטחון
        if ! bash "$script"; then
            echo "❌ Bash test FAILED: $script"
            FAILED_TESTS+=("$script")
            OVERALL_STATUS=1
        fi

    else
        echo "❌ Unknown test type: $script"
        FAILED_TESTS+=("$script: Unknown type")
        OVERALL_STATUS=1
    fi
done


###############################################
# HANDLE CI RESULT
###############################################

if [ "$OVERALL_STATUS" -ne 0 ]; then
    echo "🚨 CI Pipeline FAILED!"

    # 1. Rollback code (Reset to last known good commit hash)
    # NOTE: This is destructive. Ensure your CI server has permission.
    echo "Attempting to reset branch to previous commit..."
    # A safer way might be to find the last known good commit, but for a simple rollback:
    git reset --hard HEAD^ || {
        echo "WARNING: Could not reset to HEAD^. This is a manual check now."
        # If reset fails, we still continue to email the failure.
    }
    
    # 2. Prepare email arguments for failure
    EMAIL_ARGS=("Failure" "$BRANCH" "$PUSHER" "$TEAM")
    for failure in "${FAILED_TESTS[@]}"; do
        EMAIL_ARGS+=("$failure")
    done
    
    # Send failure email (includes failure details)
    python3 -c "from email_service import send_ci_status_email_v2; send_ci_status_email_v2('${EMAIL_ARGS[0]}', '${EMAIL_ARGS[1]}', '${EMAIL_ARGS[2]}', '${EMAIL_ARGS[3]}', *${EMAIL_ARGS[@]:4})"
    
    echo "=== CI COMPLETED WITH FAILURE ==="
    exit 1

else
    echo "✅ All tests PASSED for branch: $BRANCH"
    
    # 1. Create Pull Request to main (Placeholder: in a real environment, you'd use a GitHub/GitLab CLI or API)
    echo "Simulating creation of Pull Request from $BRANCH to main..."
    # Example: gh pr create --base main --head $BRANCH --title \"Merge $BRANCH into main after successful CI\"
    
    # 2. Send success email
    python3 -c "from email_service import send_ci_status_email_v2; send_ci_status_email_v2('Success', '$BRANCH', '$PUSHER', '$TEAM')"
    
    echo "=== CI COMPLETED ===
"
    exit 0
fi