#!/bin/bash

# Podcast Processor Setup Script
# This script sets up the directory structure and builds the Docker containers

set -e

echo "================================================"
echo "  Podcast Processor - Setup Script"
echo "================================================"
echo ""

# Define base directory
BASE_DIR="/mnt/user/appdata/podcast-processor"

# Create directory structure
echo "Creating directory structure at ${BASE_DIR}..."
mkdir -p "${BASE_DIR}/uploads"
mkdir -p "${BASE_DIR}/downloads"
mkdir -p "${BASE_DIR}/logs"
mkdir -p "${BASE_DIR}/data"

# Set permissions
echo "Setting permissions..."
chmod -R 755 "${BASE_DIR}"

echo ""
echo "Directory structure created:"
echo "  ${BASE_DIR}/uploads   - Temporary upload storage"
echo "  ${BASE_DIR}/downloads - Processed MP3 files"
echo "  ${BASE_DIR}/logs      - Application logs"
echo "  ${BASE_DIR}/data      - Encrypted credentials storage"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "ERROR: Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "Building Docker containers..."
docker-compose build

echo ""
echo "================================================"
echo "  Setup Complete!"
echo "================================================"
echo ""
echo "To start the application:"
echo "  docker-compose up -d"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f"
echo ""
echo "To stop the application:"
echo "  docker-compose down"
echo ""
echo "Access the application at:"
echo "  http://localhost:3000"
echo ""
echo "IMPORTANT - First Time Setup:"
echo "  1. Open http://localhost:3000/auth.html"
echo "  2. Configure your FileBrowser and WordPress credentials"
echo "  3. Click 'Test Connection' to verify"
echo "  4. Click 'Save & Continue'"
echo ""
echo "Backend API available at:"
echo "  http://localhost:3001"
echo ""