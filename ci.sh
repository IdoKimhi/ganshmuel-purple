#!/bin/bash

echo "Fetching latest changes from Git..."
git fetch --all

# Check for latest code and ensure images are built
echo "Building and starting CI Service in detached mode (-d)..."
docker compose -f devops/docker-compose-ci-server.yml up -d --build --force-recreate

echo "Building and starting Production Environment in detached mode (-d)..."
docker compose -f devops/docker-compose-prod.yml up -d --build --force-recreate

echo "------------------------------------------------------"
echo "CI Service (Port 8080) and Production Environment are now running."
echo "------------------------------------------------------"