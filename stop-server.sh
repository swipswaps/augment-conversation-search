#!/bin/bash
# Stop Augment Conversation Manager Web Server

echo "🛑 Stopping Augment Conversation Manager"

if pgrep -f "python3 api_server.py" > /dev/null; then
    pkill -f "python3 api_server.py"
    echo "✅ Server stopped"
else
    echo "⚠️  Server not running"
fi
