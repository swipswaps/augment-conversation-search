#!/bin/bash
# Start Augment Conversation Manager Web Server

echo "🚀 Starting Augment Conversation Manager"
echo "=========================================="
echo ""

# Check if services are running
if ! docker ps | grep -q marketplace-postgres; then
    echo "⚠️  PostgreSQL not running. Make sure marketplace-bulk-editor services are running."
    echo "Run: cd .. && docker compose up -d"
    exit 1
fi

# Install Python dependencies if needed
if ! python3 -c "import flask" 2>/dev/null; then
    echo "📦 Installing Python dependencies..."
    pip3 install -r requirements-conversation-manager.txt
    echo ""
fi

# Check if already running
if pgrep -f "python3 api_server.py" > /dev/null; then
    echo "⚠️  Server already running!"
    echo "To stop: ./stop-server.sh"
    exit 1
fi

echo "🌐 Starting API server on http://localhost:5001"
echo "📊 Web UI will be available at http://localhost:5001/"
echo "📝 Logs: tail -f api_server.log"
echo ""

# Start server in background with nohup
nohup python3 api_server.py > api_server.log 2>&1 &
SERVER_PID=$!

# Wait for server to start
sleep 3

# Check if server is running
if ps -p $SERVER_PID > /dev/null; then
    echo "✅ Server started successfully (PID: $SERVER_PID)"
    echo "🌐 Open: http://localhost:5001/"
    echo ""
    echo "To stop: ./stop-server.sh"
    echo "To view logs: tail -f api_server.log"
else
    echo "❌ Server failed to start. Check api_server.log for errors."
    exit 1
fi
