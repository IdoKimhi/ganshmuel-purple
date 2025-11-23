#!/bin/bash

BRANCH=$1

echo "=== CI STARTED ==="
echo "Branch from webhook: $BRANCH"

# Always update ALL project code
echo "Pulling latest code..."
git fetch --all
git checkout devops
git pull origin $BRANCH

# Create network for services
echo "Ensuring network exists..."
docker network create ci-network || true

echo "Running TEST environment..."
docker compose -f docker-compose.test.yml down
docker compose -f docker-compose.test.yml up -d --build

echo "Running tests..."
if bash tests/run_tests.sh; then
    echo "Tests PASSED"

    # Only main gets deployment
    if [ "$BRANCH" = "main" ]; then
        echo "Deploying to production..."
        docker compose -f docker-compose.prod.yml down
        docker compose -f docker-compose.prod.yml up -d --build
    fi

    python3 send_mail.py "Success" "$BRANCH"

else
    echo "Tests FAILED"
    python3 send_mail.py "Failure" "$BRANCH"
    exit 1
fi
