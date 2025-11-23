#!/bin/bash

# This is the main startup script for the entire CI/CD environment.
# It is used for initial setup AND for self-update of the CI service.

echo "--- CI/CD System Startup Script ---"

echo "1. Getting latest changes from Git..."
# Use git pull --rebase to fetch new changes and update local files.
# This is CRITICAL for self-update, as it pulls the new code (including the new app.py)
# before the Docker image is rebuilt.
git pull --rebase || { echo "ERROR: Git pull failed. Stopping startup process."; exit 1; }

# Assuming the compose files are in a 'devops' subdirectory relative to where ci.sh is executed.
CI_COMPOSE="devops/docker-compose-ci-server.yml"
PROD_COMPOSE="devops/docker-compose-prod.yml"

echo "2. Building and starting CI Service in detached mode (-d)..."
# This brings up the CI server with the latest code, rebuilding the image if necessary.
# We also tear down the old one in case it was left running (app.py pre-emptively handles this too).
docker compose -f $CI_COMPOSE down
docker compose -f $CI_COMPOSE up -d --build --force-recreate

echo "3. Building and starting Production Environment in detached mode (-d)..."
# This ensures the Production environment is running constantly.
# We assume docker-compose-prod.yml exists and defines the app stack.
docker compose -f $PROD_COMPOSE up -d --build --force-recreate
#
echo "------------------------------------------------------"
echo "CI Service (Port 8080) and Production Environment are now running."
echo "------------------------------------------------------"