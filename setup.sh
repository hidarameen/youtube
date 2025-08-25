#!/bin/bash

# =================================
# Ultra High-Performance Video Downloader Bot
# Setup Script
# =================================

set -e

echo "🚀 Setting up Ultra High-Performance Video Downloader Bot..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    print_status "Creating .env file from template..."
    cp .env.example .env
    print_warning "Please edit .env file with your actual configuration values"
else
    print_success ".env file already exists"
fi

# Create necessary directories
print_status "Creating necessary directories..."
mkdir -p temp logs downloads

# Set proper permissions
print_status "Setting up permissions..."
chmod +x setup.sh
chmod 755 temp logs downloads

# Build and start the services
print_status "Building Docker images..."
docker-compose build

print_status "Starting services..."
docker-compose up -d

# Wait for services to be ready
print_status "Waiting for services to be ready..."
sleep 10

# Check if services are running
if docker-compose ps | grep -q "Up"; then
    print_success "Services are running successfully!"
    
    echo ""
    echo "🎉 Setup completed successfully!"
    echo ""
    echo "📋 Next steps:"
    echo "1. Edit .env file with your bot token and configuration"
    echo "2. Run: docker-compose restart video_bot"
    echo "3. Check logs: docker-compose logs -f video_bot"
    echo ""
    echo "🌐 Management interfaces:"
    echo "- pgAdmin: http://localhost:8080"
    echo "- Redis Commander: http://localhost:8081"
    echo ""
    echo "📊 To view logs:"
    echo "docker-compose logs -f video_bot"
    echo ""
    echo "🛑 To stop services:"
    echo "docker-compose down"
    
else
    print_error "Some services failed to start. Check the logs:"
    print_error "docker-compose logs"
fi