# Repository Information

## GitHub Repository

**Repository**: https://github.com/swipswaps/augment-conversation-search

**Description**: PostgreSQL-based conversation manager with full-text search, fuzzy matching, autocomplete, and modern web UI. Features trigram-based typo tolerance, 'did you mean' suggestions, and message-level search with contextual snippets.

## Repository Structure

This is a **standalone repository** created from the `augment-conversation-manager` directory. It has its own `.git` directory and is completely independent from the parent `marketplace-bulk-editor` repository.

### Local Path
```
/home/owner/Documents/694533e8-ac54-8329-bbf9-22069a0d424e/marketplace-bulk-editor/augment-conversation-manager
```

### Git Configuration
- **Remote**: origin → https://github.com/swipswaps/augment-conversation-search.git
- **Branch**: main
- **Initial Commit**: 2f74ee3

## Key Features Included

### 1. Fuzzy Search Implementation
- PostgreSQL `pg_trgm` extension for trigram matching
- Automatic fallback to fuzzy search when exact matches fail
- "Did you mean" suggestions for typos
- Migration scripts in `migrations/` directory

### 2. Full-Text Search
- ts_vector indexing for fast text search
- Message-level search with contextual snippets
- Code/prose snippet classification
- Syntax highlighting with Prism.js

### 3. Modern Web UI
- Real-time search with debouncing
- Keyboard navigation (↑↓ arrows, Enter, Esc)
- Visual search type indicators
- Responsive design

### 4. API Server
- Flask-based REST API
- PostgreSQL + Redis backend
- Schema enforcement for responses
- Autocomplete endpoint

### 5. Testing Framework
- UX compliance tests
- Schema enforcement tests
- Snippet extraction tests
- E2E testing with Cypress

## Documentation Files

- `README.md` - Main project documentation
- `FUZZY_SEARCH_README.md` - Fuzzy search implementation guide
- `API_DOCUMENTATION_UPDATE.md` - API reference
- `PRODUCTION_DEPLOYMENT_CHECKLIST.md` - Deployment guide
- `PERFORMANCE_ANALYSIS.md` - Performance metrics

## Quick Start

1. **Setup Database**:
   ```bash
   docker-compose -f docker-compose-conversation-manager.yml up -d
   ```

2. **Run Migrations**:
   ```bash
   docker exec -i marketplace-postgres psql -U marketplace_user -d augment_conversations < migrations/0_pre_migration_check.sql
   docker exec -i marketplace-postgres psql -U marketplace_user -d augment_conversations < migrations/1_database_fuzzy_setup.sql
   ```

3. **Start Server**:
   ```bash
   ./start-server.sh
   ```

4. **Access UI**:
   ```
   http://localhost:5001
   ```

## Git Commands

### Clone Repository
```bash
git clone https://github.com/swipswaps/augment-conversation-search.git
cd augment-conversation-search
```

### Pull Latest Changes
```bash
git pull origin main
```

### Push Changes
```bash
git add .
git commit -m "Your commit message"
git push origin main
```

## Important Notes

1. **Independent Repository**: This repository is completely separate from the parent `marketplace-bulk-editor` repository.

2. **No Breaking Changes**: Creating this repository did not affect the parent repository or any other projects.

3. **Database**: Requires PostgreSQL 15+ with `pg_trgm` extension.

4. **Python Version**: Tested with Python 3.14.

5. **Dependencies**: See `requirements-conversation-manager.txt` for Python packages.

## Support

For issues or questions, please create an issue on GitHub:
https://github.com/swipswaps/augment-conversation-search/issues

## License

See LICENSE file in the repository.

