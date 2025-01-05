#!/bin/bash

# Pull the latest changes from the repository
git pull

# Stop and remove the containers defined in the docker-compose file
docker-compose down

# Build and start the containers in detached mode
docker-compose up --build -d