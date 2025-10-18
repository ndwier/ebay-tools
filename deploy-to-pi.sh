#!/bin/bash
# Quick deployment script for Raspberry Pi
# Run this script ON YOUR RASPBERRY PI

set -e

echo "🍓 eBay Automation - Raspberry Pi Deployment"
echo "=============================================="
echo ""

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "⚠️  Warning: This doesn't appear to be a Raspberry Pi"
    echo "   Continuing anyway..."
    echo ""
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "📦 Docker not found. Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo "✅ Docker installed!"
    echo "⚠️  You may need to log out and back in for Docker permissions to take effect"
    echo ""
else
    echo "✅ Docker is installed"
fi

# Check if Docker Compose is available
if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose not available"
    echo "   Install with: sudo apt-get install docker-compose-plugin"
    exit 1
else
    echo "✅ Docker Compose is available"
fi

echo ""
echo "📥 Cloning repository..."

# Clone or pull the repository
if [ -d "$HOME/ebay-tools" ]; then
    echo "   Repository already exists. Updating..."
    cd $HOME/ebay-tools
    git pull
else
    cd $HOME
    git clone https://github.com/ndwier/ebay-tools.git
    cd ebay-tools
fi

echo "✅ Repository ready"
echo ""

# Check for .env file
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp env_template.txt .env
    echo "✅ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: You need to edit the .env file with your eBay credentials!"
    echo ""
    echo "   Run: nano .env"
    echo ""
    echo "   You need to fill in:"
    echo "   - EBAY_APP_ID"
    echo "   - EBAY_CERT_ID"
    echo "   - EBAY_DEV_ID"
    echo "   - EBAY_TOKEN"
    echo ""
    read -p "Press Enter after you've edited the .env file..."
else
    echo "✅ .env file already exists"
fi

echo ""
echo "🐳 Building Docker container..."
docker compose build

echo ""
echo "🚀 Starting eBay Automation..."
docker compose up -d

echo ""
echo "⏳ Waiting for container to start..."
sleep 5

# Check if container is running
if docker compose ps | grep -q "Up"; then
    echo "✅ Container is running!"
    
    # Get the Pi's IP address
    PI_IP=$(hostname -I | awk '{print $1}')
    
    echo ""
    echo "======================================"
    echo "🎉 Deployment Complete!"
    echo "======================================"
    echo ""
    echo "📊 Dashboard: http://$PI_IP:5001"
    echo "📊 From this Pi: http://localhost:5001"
    echo ""
    echo "🔍 View logs: docker compose logs -f"
    echo "🔄 Restart: docker compose restart"
    echo "🛑 Stop: docker compose down"
    echo ""
    echo "🌐 Next Steps:"
    echo "   1. Open the dashboard in your browser"
    echo "   2. Click 'Sync Listings' to import your eBay items"
    echo "   3. Check the activity logs"
    echo "   4. Verify scheduled jobs are running"
    echo ""
    echo "📚 Documentation: ~/ebay-tools/README.md"
    echo ""
else
    echo "❌ Container failed to start"
    echo ""
    echo "Check logs with: docker compose logs"
    exit 1
fi

