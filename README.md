# 🚀 Augment Conversation Manager

**Web-based tool to manage, search, and browse Augment conversation exports with PostgreSQL storage and Redis caching.**

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)

---

## ✨ Features

- 📊 **PostgreSQL Storage** - Persistent conversation data with full-text search
- 📦 **Redis Caching** - Fast access with write-through cache
- 🔍 **Deduplication** - SHA256 content hashing prevents duplicate imports
- 🌐 **Web Interface** - Beautiful responsive UI to browse conversations
- 🔎 **Full-Text Search** - Find conversations by name instantly
- 📈 **Statistics Dashboard** - View database and cache metrics
- 🐳 **Docker Deployment** - One-command setup with Docker Compose

---

## 🚀 Quick Start

### 1. Start the Services

```bash
./setup-conversation-manager.sh
```

This will:
- Start PostgreSQL and Redis in Docker containers
- Create database schema
- Install Python dependencies

### 2. Import Your Conversations

```bash
python3 conversation_manager.py import "conversation_export_INDEX.json"
```

Replace `conversation_export_INDEX.json` with your actual Augment conversation export file.

**Import multiple files:**
```bash
python3 conversation_manager.py import "conversation1.json"
python3 conversation_manager.py import "conversation2.json"
```

### 3. Start the Web Server

```bash
./start-server.sh
```

### 4. Open the Web UI

Open your browser to: **http://localhost:5001**

You'll see:
- List of all imported conversations
- Search bar to filter by name
- Click any conversation to view full messages
- Statistics dashboard showing database metrics

---

## 📖 Usage Examples

### Import a Conversation

```bash
python3 conversation_manager.py import "Accessibility_Upgrade_2026-01-05.json"
```

**Output:**
```
✅ Connected to PostgreSQL: localhost:5432/augment_conversations
✅ Connected to Redis: localhost:6379/0

📖 Reading Accessibility_Upgrade_2026-01-05.json...
📊 Conversation: Accessibility Upgrade for Login Controls
   ID: 5f9624e7-46a7-40f2-afad-8615d839c692
   Messages: 5590
   Tool states: 4896
✅ New conversation - importing...
✅ Import complete!
```

### Search Conversations (CLI)

```bash
python3 conversation_manager.py search "accessibility"
```

### View Statistics (CLI)

```bash
python3 conversation_manager.py stats
```

**Output:**
```
📊 Database Statistics:
   Total conversations: 3
   Total messages: 15,234
   Total tool states: 12,456
   Total storage: 125.34 MB

📦 Redis Cache:
   Keys: 127
   Hit rate: 73.0%
```

### Get Full Conversation (CLI)

```bash
python3 conversation_manager.py get "5f9624e7-46a7-40f2-afad-8615d839c692" --output backup.json
```

---

## 🌐 Web API Endpoints

The API server runs on `http://localhost:5001` and provides:

- `GET /api/conversations` - List all conversations
- `GET /api/conversations/<id>` - Get full conversation data
- `GET /api/messages/<id>` - Get messages for a conversation
- `GET /api/search?q=<query>` - Search conversations
- `GET /api/stats` - Get database statistics
- `GET /api/health` - Health check

---

## 🐳 Docker Services

The system uses two Docker containers:

- **PostgreSQL 15** - Database on port 5432
- **Redis 7** - Cache on port 6379

**View running containers:**
```bash
docker-compose -f docker-compose-conversation-manager.yml ps
```

**Stop services:**
```bash
docker-compose -f docker-compose-conversation-manager.yml down
```

**Reset everything:**
```bash
docker-compose -f docker-compose-conversation-manager.yml down -v
./setup-conversation-manager.sh
```

---

## 📁 File Structure

```
augment-conversation-manager/
├── conversation_manager.py          # Core Python library
├── api_server.py                    # Flask REST API server
├── schema.sql                       # PostgreSQL schema
├── docker-compose-conversation-manager.yml
├── setup-conversation-manager.sh    # Setup script
├── start-server.sh                  # Start web server
├── requirements-conversation-manager.txt
├── test-conversation-manager.py     # Test suite
├── web/
│   ├── app.html                     # Web UI
│   └── app.js                       # Frontend JavaScript
└── README.md
```

---

## 🧪 Testing

```bash
python3 test-conversation-manager.py
```

This runs 6 comprehensive tests:
- Import conversation
- Duplicate detection
- Search functionality
- Get conversation
- Statistics
- Redis caching

---

## 🔧 Troubleshooting

### "Connection refused" Error

**Problem:** PostgreSQL/Redis not running

**Solution:**
```bash
docker-compose -f docker-compose-conversation-manager.yml up -d
sleep 10
```

### "No module named 'flask'" Error

**Problem:** Python dependencies not installed

**Solution:**
```bash
pip3 install -r requirements-conversation-manager.txt
```

### Web UI Shows "Could not connect to API"

**Problem:** API server not running

**Solution:**
```bash
./start-server.sh
```

---

## 📄 License

MIT License - see LICENSE file for details

---

## 🤝 Contributing

Issues and pull requests welcome at: https://github.com/swipswaps/marketplace-bulk-editor

