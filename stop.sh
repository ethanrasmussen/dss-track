#!/bin/bash

echo "Stopping DSS-TRACK..."
docker-compose down

echo ""
echo "Services stopped successfully!"
echo ""
echo "To remove all data volumes, run: docker-compose down -v"
