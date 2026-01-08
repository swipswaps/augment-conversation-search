#!/bin/bash
# Setup script for Augment Conversation Data Manager

set -e

echo "🚀 Setting up Augment Conversation Data Manager..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose is not installed. Please install docker-compose first."
    exit 1
fi

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8+ first."
    exit 1
fi

echo "✅ Prerequisites check passed"

# Start Docker services
echo ""
echo "📦 Starting PostgreSQL and Redis..."
docker-compose -f docker-compose-conversation-manager.yml up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check PostgreSQL
echo "🔍 Checking PostgreSQL..."
until docker exec augment-postgres pg_isready -U postgres &> /dev/null; do
    echo "   Waiting for PostgreSQL..."
    sleep 2
done
echo "✅ PostgreSQL is ready"

# Check Redis
echo "🔍 Checking Redis..."
until docker exec augment-redis redis-cli ping &> /dev/null; do
    echo "   Waiting for Redis..."
    sleep 2
done
echo "✅ Redis is ready"

# Install Python dependencies
echo ""
echo "📦 Installing Python dependencies..."
pip3 install -r requirements-conversation-manager.txt

echo ""
echo "✅ Setup complete!"
echo ""
echo "📚 Next steps:"
echo "   1. Import a conversation:"
echo "      python3 conversation_manager.py import your-export.json"
echo ""
echo "   2. Search conversations:"
echo "      python3 conversation_manager.py search 'query'"
echo ""
echo "   3. View statistics:"
echo "      python3 conversation_manager.py stats"
echo ""
echo "   4. Read the full documentation:"
echo "      cat CONVERSATION_MANAGER_README.md"
echo ""

