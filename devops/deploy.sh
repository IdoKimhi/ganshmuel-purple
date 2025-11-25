#!/bin/bash

BRANCH=$1
PUSHER=${2:-"ci_user"}  # Default value if not provided
TEAM=${3:-"devops"}     # Default value if not provided

echo "=== CI STARTED ==="
echo "Branch from webhook: $BRANCH"
echo "Pusher: $PUSHER, Team: $TEAM"

# Note: Assuming CI is meant to run on all branches based on the log output.
if [ "$BRANCH" != "ido" ]; then # <-- CRITICAL CHANGE: Script only runs for 'ido' branch
    echo "🚨 ERROR: Deployment script only runs for 'ido' branch. Exiting."
    exit 0
fi

echo "Fixing Git repository ownership..."
# Needed in some CI environments to prevent fatal errors
git config --global --add safe.directory /app_root

echo "Pulling latest code..."
git fetch --all

# Save the current commit hash *before* pulling (for clean rollback)
PRE_PULL_COMMIT=$(git rev-parse HEAD)
echo "Pre-pull commit hash for rollback: $PRE_PULL_COMMIT"
git pull origin "$BRANCH"

# Save the latest commit hash for later in case of success (or just for logging)
LATEST_COMMIT=$(git rev-parse HEAD)
echo "Latest commit hash after pull: $LATEST_COMMIT"

echo "Ensuring network exists..."
docker network create ci-network || true

echo "Loading environment variables for Docker Compose..."
set -a
source ../weight/.env
source ../billing/.env
set +a

echo "Running TEST environment..."
docker compose -f docker-compose-test.yml down -v # Remove volumes to ensure fresh DB start
docker compose -f docker-compose-test.yml up -d --build


###############################################
# SELECT TESTS BASED ON BRANCH (Simplified for 'dev')
###############################################
echo "Selecting test scripts..."
# When pushing to any branch, we assume all core tests should run
TEST_SCRIPTS=(
    "../weight/e2e_test.py"
    "../billing/test_billing.sh"
)

# Array to track failed tests for the email body
FAILED_TESTS=()
OVERALL_STATUS="Success"
PRE_PULL_COMMIT_HASH="$PRE_PULL_COMMIT" # Use the commit saved earlier


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
            FAILED_TESTS+=("Python Test (Health Check) FAILED: $script")
            OVERALL_STATUS="Failure"
            # continue to run other tests, but set overall status to Failure
        fi

    # If Bash
    elif [[ "$script" == *.sh ]]; then
        echo "→ Running Bash test"
        chmod +x "$script"   # Ensure it's executable
        if ! bash "$script"; then
            echo "❌ Bash test FAILED: $script"
            FAILED_TESTS+=("Bash Test FAILED: $script")
            OVERALL_STATUS="Failure"
            # continue to run other tests, but set overall status to Failure
        fi

    else
        echo "❌ Unknown test type: $script"
        FAILED_TESTS+=("Unknown Test Type: $script")
        OVERALL_STATUS="Failure"
    fi
done

# Cleanup the test environment regardless of success/failure
echo "Stopping and cleaning up test environment..."
docker compose -f docker-compose-test.yml down -v


###############################################
# FAILURE / SUCCESS HANDLER
###############################################
if [ "$OVERALL_STATUS" = "Failure" ]; then
    echo "!!! CI FAILURE DETECTED !!!"
    
    # 1. Rollback logic
    # Change directory to the root of the Git repo (assuming /app_root is the root)
    cd /app_root || exit
    
    # Reset the repository to the last known good commit (PRE_PULL_COMMIT saved before pull)
    echo "Attempting to reset branch $BRANCH to previous state (commit: $PRE_PULL_COMMIT)..."
    # Note: We are now commenting out the actual git reset to prevent permission/remote issues 
    # but print a warning as planned.
    # git reset --hard "$PRE_PULL_COMMIT" || {
        echo "WARNING: Could not reset to $PRE_PULL_COMMIT. Manual intervention required."
    # }
    
    # Return to the original working directory
    cd devops
    
    # 2. Prepare email arguments for failure
    # Quotes are needed around each argument for the shell array.
    EMAIL_ARGS=("'Failure'" "'$BRANCH'" "'$PUSHER'" "'$TEAM'")
    
    # Add each failed test as a separately quoted string argument for Python
    # This prevents the "invalid syntax" error.
    for failure in "${FAILED_TESTS[@]}"; do
        EMAIL_ARGS+=("'$failure'")
    done
    
    # Construct the final python command string
    # We use a space-separated list of arguments inside the shell command.
    PYTHON_CMD="from email_service import send_ci_status_email_v2; send_ci_status_email_v2(${EMAIL_ARGS[@]})"
    
    echo "Running failure email script: python3 -c \"$PYTHON_CMD\""
    # Send failure email (includes failure details)
    python3 -c "$PYTHON_CMD"
    
    echo "=== CI COMPLETED WITH FAILURE ==="
    exit 1

else
    echo "✅ All tests PASSED for branch: $BRANCH"
    
    # 1. Create Pull Request to main (Placeholder: in a real environment, you'd use a GitHub/GitLab CLI or API)
    echo "Simulating creation of Pull Request from $BRANCH to main..."
    
    # 2. Send success email
    PYTHON_CMD="from email_service import send_ci_status_email_v2; send_ci_status_email_v2('Success', '$BRANCH', '$PUSHER', '$TEAM', 'Pull Request simulation successful.')"
    echo "Running success email script: python3 -c \"$PYTHON_CMD\""
    python3 -c "$PYTHON_CMD"
    
    echo "=== CI COMPLETED WITH SUCCESS ==="
    exit 0
fi