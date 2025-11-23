#!/bin/bash

BRANCH=$1

echo "Running test environment..."
docker compose -f docker-compose.test.yml down
docker compose -f docker-compose.test.yml up -d --build

echo "Running tests..."
if bash tests/run_tests.sh; then
    echo "Tests PASSED"
    

    if [ "$BRANCH" = "master" ]; then
        echo "Deploying to production..."
        docker compose -f docker-compose.prod.yml down
        docker compose -f docker-compose.prod.yml up -d --build
    fi
    
    python send_mail.py "Success" "$BRANCH"

else
    echo "Tests FAILED"
    python send_mail.py "Failure" "$BRANCH"
    exit 1
fi
