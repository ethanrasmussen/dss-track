#!/bin/bash

echo "Building DSS-TRACK..."
echo "======================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Build and start containers
echo "Building Docker containers..."
docker-compose build

echo ""
echo "Starting services..."
docker-compose up -d

echo ""
echo "Waiting for services to be healthy..."
sleep 5

# Check service status
echo ""
echo "Service Status:"
echo "---------------"
docker-compose ps

echo ""
echo "======================================="
echo "Application is ready!"
echo ""
echo "Frontend: http://localhost:3100"
echo "Backend API: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "To view logs: docker-compose logs -f"
echo "To stop: docker-compose down"
echo "======================================="
