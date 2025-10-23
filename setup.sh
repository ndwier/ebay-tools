#!/bin/bash
# Quick setup script for eBay Store Automation

set -e

echo "🛒 eBay Store Automation - Setup"
echo "================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed!"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed!"
    echo "Please install Docker Compose first: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp env_template.txt .env
    echo "✅ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Please edit the .env file with your eBay API credentials!"
    echo "   Run: nano .env"
    echo ""
    read -p "Press Enter after you've configured your .env file..."
else
    echo "✅ .env file already exists"
fi

# Create necessary directories
echo ""
echo "📁 Creating data and logs directories..."
mkdir -p data logs
echo "✅ Directories created"

# Build and start the container
echo ""
echo "🐳 Building Docker container..."
docker-compose build

echo ""
echo "🚀 Starting eBay Store Automation..."
docker-compose up -d

echo ""
echo "✅ Setup complete!"
echo ""
echo "📊 Access your dashboard at: http://localhost:5001"
echo "📋 View logs with: docker-compose logs -f"
echo "🛑 Stop the service with: docker-compose down"
echo ""
echo "Happy automating! 🎉"


