#!/usr/bin/env python3
"""
Augment Conversation Data Manager
Manages conversation exports with Redis caching and PostgreSQL storage.
Includes deduplication, search, and analytics.

Based on:
- Redis write-through caching pattern (redis.io/tutorials)
- PostgreSQL JSONB best practices
- Content-based deduplication using SHA256 hashes
"""

import json
import hashlib
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor, Json
import redis


class ConversationManager:
    """
    Manages Augment conversation data with Redis caching and PostgreSQL storage.
    
    Features:
    - Write-through caching (Redis + PostgreSQL)
    - Content-based deduplication using SHA256 hashes
    - Full-text search on conversation names
    - JSONB querying for flexible data access
    - Automatic cache invalidation
    """
    
    def __init__(
        self,
        pg_host: str = "localhost",
        pg_port: int = 5432,
        pg_database: str = "augment_conversations",
        pg_user: str = "marketplace_user",
        pg_password: str = "marketplace_pass",
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        cache_ttl: int = 3600  # 1 hour default
    ):
        """Initialize connections to PostgreSQL and Redis."""
        # PostgreSQL connection
        self.pg_conn = psycopg2.connect(
            host=pg_host,
            port=pg_port,
            database=pg_database,
            user=pg_user,
            password=pg_password
        )
        self.pg_conn.autocommit = False
        
        # Redis connection
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=False  # We'll handle encoding
        )
        
        self.cache_ttl = cache_ttl
        
        print(f"✅ Connected to PostgreSQL: {pg_host}:{pg_port}/{pg_database}")
        print(f"✅ Connected to Redis: {redis_host}:{redis_port}/{redis_db}")
    
    def __del__(self):
        """Clean up connections."""
        if hasattr(self, 'pg_conn'):
            self.pg_conn.close()
        if hasattr(self, 'redis_client'):
            self.redis_client.close()
    
    @staticmethod
    def compute_hash(data: Any) -> str:
        """Compute SHA256 hash of data for deduplication."""
        if isinstance(data, dict) or isinstance(data, list):
            data_str = json.dumps(data, sort_keys=True)
        else:
            data_str = str(data)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def _get_cache_key(self, key_type: str, identifier: str) -> str:
        """Generate Redis cache key."""
        return f"augment:{key_type}:{identifier}"
    
    def _cache_get(self, key: str) -> Optional[Dict]:
        """Get data from Redis cache."""
        data = self.redis_client.get(key)
        if data:
            return json.loads(data)
        return None
    
    def _cache_set(self, key: str, data: Dict, ttl: Optional[int] = None):
        """Set data in Redis cache with TTL."""
        if ttl is None:
            ttl = self.cache_ttl
        self.redis_client.setex(key, ttl, json.dumps(data))
    
    def _cache_delete(self, pattern: str):
        """Delete cache keys matching pattern."""
        keys = self.redis_client.keys(pattern)
        if keys:
            self.redis_client.delete(*keys)
    
    def import_conversation(self, export_file: str) -> Dict[str, Any]:
        """
        Import Augment conversation export with deduplication.
        
        Uses write-through caching:
        1. Check if conversation already exists (by content hash)
        2. If duplicate, return existing conversation ID
        3. If new, write to PostgreSQL and cache in Redis
        
        Args:
            export_file: Path to Augment conversation export JSON
            
        Returns:
            Dict with import results (conversation_id, is_duplicate, stats)
        """
        print(f"\n📖 Reading {export_file}...")
        
        with open(export_file, 'r') as f:
            data = json.load(f)
        
        conversation = data.get('conversation', {})
        version = data.get('version', '1.0.0')
        exported_at = data.get('exportedAt')
        
        # Extract conversation metadata
        conv_id = conversation.get('id')
        name = conversation.get('name', 'Untitled')
        created_at = conversation.get('createdAtIso')
        last_interacted_at = conversation.get('lastInteractedAtIso')
        chat_history = conversation.get('chatHistory', [])
        tool_use_states = conversation.get('toolUseStates', {})
        metadata = {
            'version': version,
            'personaType': conversation.get('personaType'),
            'draftActiveContextIds': conversation.get('draftActiveContextIds', []),
            'extraData': conversation.get('extraData', {})
        }
        
        # Compute content hash for deduplication
        content_hash = self.compute_hash(conversation)
        file_size_mb = os.path.getsize(export_file) / (1024 * 1024)
        
        print(f"📊 Conversation: {name}")
        print(f"   ID: {conv_id}")
        print(f"   Messages: {len(chat_history)}")
        print(f"   Tool states: {len(tool_use_states)}")
        print(f"   Content hash: {content_hash[:16]}...")
        
        # Check cache first
        cache_key = self._get_cache_key("conversation", conv_id)
        cached = self._cache_get(cache_key)
        if cached:
            print(f"✅ Found in cache")
            return {
                'conversation_id': cached['id'],
                'is_duplicate': True,
                'source': 'cache',
                'stats': cached
            }

        # Check database for duplicate (by content hash)
        cursor = self.pg_conn.cursor(cursor_factory=RealDictCursor)

        try:
            cursor.execute(
                "SELECT id, conversation_id, name, total_messages, total_tool_states "
                "FROM conversations WHERE content_hash = %s",
                (content_hash,)
            )
            existing = cursor.fetchone()

            if existing:
                print(f"⚠️  Duplicate detected (content hash match)")
                print(f"   Existing conversation: {existing['name']}")

                # Cache the existing conversation
                self._cache_set(cache_key, dict(existing))

                return {
                    'conversation_id': str(existing['id']),
                    'is_duplicate': True,
                    'source': 'database',
                    'stats': dict(existing)
                }

            # Not a duplicate - insert new conversation
            print(f"✅ New conversation - importing...")

            cursor.execute(
                """
                INSERT INTO conversations (
                    conversation_id, name, created_at, last_interacted_at,
                    exported_at, total_messages, total_tool_states,
                    file_size_mb, content_hash, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    conv_id, name, created_at, last_interacted_at,
                    exported_at, len(chat_history), len(tool_use_states),
                    file_size_mb, content_hash, Json(metadata)
                )
            )

            db_conv_id = cursor.fetchone()['id']

            # Import chat history
            print(f"   Importing {len(chat_history)} messages...")
            message_count = 0
            duplicate_messages = 0

            for idx, message in enumerate(chat_history):
                msg_hash = self.compute_hash(message)

                try:
                    cursor.execute(
                        """
                        INSERT INTO chat_history (
                            conversation_id, message_index, role, content,
                            content_hash, timestamp
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            db_conv_id, idx,
                            message.get('role', 'unknown'),
                            Json(message),
                            msg_hash,
                            message.get('timestamp')
                        )
                    )
                    message_count += 1
                except psycopg2.IntegrityError:
                    # Duplicate message (content_hash already exists)
                    duplicate_messages += 1
                    self.pg_conn.rollback()
                    cursor = self.pg_conn.cursor(cursor_factory=RealDictCursor)

            print(f"   ✅ Imported {message_count} messages ({duplicate_messages} duplicates skipped)")

            # Import tool use states
            print(f"   Importing {len(tool_use_states)} tool states...")
            tool_count = 0
            duplicate_tools = 0

            for tool_id, tool_data in tool_use_states.items():
                tool_hash = self.compute_hash(tool_data)

                try:
                    cursor.execute(
                        """
                        INSERT INTO tool_use_states (
                            conversation_id, tool_use_id, request_id,
                            phase, result, content_hash
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            db_conv_id, tool_id,
                            tool_data.get('requestId'),
                            tool_data.get('phase'),
                            Json(tool_data.get('result', {})),
                            tool_hash
                        )
                    )
                    tool_count += 1
                except psycopg2.IntegrityError:
                    # Duplicate tool state
                    duplicate_tools += 1
                    self.pg_conn.rollback()
                    cursor = self.pg_conn.cursor(cursor_factory=RealDictCursor)

            print(f"   ✅ Imported {tool_count} tool states ({duplicate_tools} duplicates skipped)")

            # Commit transaction
            self.pg_conn.commit()

            # Cache the new conversation
            conv_data = {
                'id': str(db_conv_id),
                'conversation_id': conv_id,
                'name': name,
                'total_messages': message_count,
                'total_tool_states': tool_count
            }
            self._cache_set(cache_key, conv_data)

            print(f"✅ Import complete!")

            return {
                'conversation_id': str(db_conv_id),
                'is_duplicate': False,
                'source': 'new',
                'stats': {
                    'messages_imported': message_count,
                    'messages_duplicates': duplicate_messages,
                    'tools_imported': tool_count,
                    'tools_duplicates': duplicate_tools
                }
            }

        except Exception as e:
            self.pg_conn.rollback()
            print(f"❌ Error importing conversation: {e}")
            raise
        finally:
            cursor.close()

    def search_conversations(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Search conversations by name OR message content using materialized search_vector.
        Uses PostgreSQL GIN index for fast full-text search.
        Results are cached in Redis.
        """
        # Check cache
        cache_key = self._get_cache_key("search", hashlib.md5(query.encode()).hexdigest())
        cached = self._cache_get(cache_key)
        if cached:
            print(f"✅ Search results from cache")
            return cached

        cursor = self.pg_conn.cursor(cursor_factory=RealDictCursor)

        try:
            # Search using materialized search_vector column (uses GIN index)
            cursor.execute(
                """
                SELECT id, conversation_id, name, created_at, last_interacted_at,
                       total_messages, total_tool_states, file_size_mb
                FROM conversations
                WHERE name ILIKE %s

                UNION

                SELECT DISTINCT c.id, c.conversation_id, c.name, c.created_at, c.last_interacted_at,
                       c.total_messages, c.total_tool_states, c.file_size_mb
                FROM conversations c
                INNER JOIN chat_history ch ON c.id = ch.conversation_id
                WHERE ch.search_vector @@ plainto_tsquery('english', %s)

                ORDER BY last_interacted_at DESC
                LIMIT %s
                """,
                (f"%{query}%", query, limit)
            )

            results = [dict(row) for row in cursor.fetchall()]

            # Convert datetime and Decimal to JSON-serializable types
            for result in results:
                result['created_at'] = result['created_at'].isoformat() if result['created_at'] else None
                result['last_interacted_at'] = result['last_interacted_at'].isoformat() if result['last_interacted_at'] else None
                result['id'] = str(result['id'])
                result['file_size_mb'] = float(result['file_size_mb']) if result['file_size_mb'] else 0.0

            # Cache results
            self._cache_set(cache_key, results, ttl=300)  # 5 minutes

            return results

        except Exception as e:
            # Rollback transaction on error to prevent "transaction aborted" state
            self.pg_conn.rollback()
            raise e

        except Exception as e:
            # Rollback transaction on error to prevent "transaction aborted" state
            self.pg_conn.rollback()
            raise e

        finally:
            cursor.close()

    def normalize_message_content(self, raw) -> str:
        """
        PRF-DATA-SHAPE-001: Database Boundary Normalization

        HARD INVARIANTS:
        - All downstream logic receives a guaranteed non-empty string
        - Anything else is a fatal error
        - This is the ONLY entry point for message content into the system
        - No function may assume the shape of database output

        VERACITY CHECKS:
        - Input type validation (str, dict, or reject)
        - Output is non-empty string
        - No silent fallbacks or defaults
        """
        # VERACITY CHECK 1: Not None
        if raw is None:
            raise RuntimeError("Message content is None")

        # VERACITY CHECK 2: Type is str or dict
        if isinstance(raw, str):
            text = raw.strip()
        elif isinstance(raw, dict):
            # Try multiple known keys in order of preference
            text = (
                raw.get("response_text")  # Assistant messages (Augment format)
                or raw.get("content")      # User messages or standard format
                or raw.get("text")         # Alternative format
                or ""
            ).strip()
        else:
            # Reject unsupported types loudly
            raise RuntimeError(
                f"Unsupported content type: {type(raw).__name__}. "
                f"Expected str or dict, got {type(raw)}"
            )

        # VERACITY CHECK 3: Result is non-empty
        if not text:
            raise RuntimeError(
                f"Normalized message content is empty. "
                f"Input type: {type(raw).__name__}, "
                f"Input keys: {list(raw.keys()) if isinstance(raw, dict) else 'N/A'}"
            )

        # VERACITY CHECK 4: Output type assertion
        assert isinstance(text, str) and len(text) > 0, \
            f"POST-CONDITION VIOLATION: normalize_message_content must return non-empty string"

        return text

    def _get_did_you_mean_suggestion(self, cursor, query: str) -> str:
        """
        Get 'did you mean' suggestion for typos using trigram similarity.

        Returns the most similar word from the corpus if similarity > 0.6.
        Returns None if no good suggestion found.
        """
        try:
            cursor.execute("""
                SELECT word, similarity(word, %s) as sim
                FROM ts_stat('SELECT search_vector FROM chat_history')
                WHERE similarity(word, %s) > 0.6
                ORDER BY sim DESC
                LIMIT 1
            """, (query, query))

            row = cursor.fetchone()
            return row['word'] if row else None
        except Exception as e:
            # If trigram search fails, return None (graceful degradation)
            import logging
            logging.warning(f"Did you mean suggestion failed: {e}")
            return None

    def _fuzzy_search_messages(
        self,
        cursor,
        query: str,
        limit: int,
        role: str = None,
        snippet_type: str = None,
        conversation_id: str = None,
        date_from: str = None,
        date_to: str = None
    ):
        """
        Fuzzy search using trigram similarity for typo tolerance.

        Uses PostgreSQL % operator (trigram similarity) to find approximate matches.
        Returns results ordered by similarity score.
        """
        where_clauses = ["content::text % %s"]
        params = [query]

        # Add filters (same as exact search)
        if role:
            where_clauses.append("role = %s")
            params.append(role)

        if conversation_id:
            where_clauses.append("conversation_id = %s")
            params.append(conversation_id)

        if date_from:
            where_clauses.append("timestamp >= %s")
            params.append(date_from)

        if date_to:
            where_clauses.append("timestamp <= %s")
            params.append(date_to)

        sql = f"""
            WITH conversation_stats AS (
                SELECT
                    conversation_id,
                    COUNT(*) as total_messages,
                    MAX(timestamp) as last_activity
                FROM chat_history
                GROUP BY conversation_id
            )
            SELECT
                ch.id AS message_id,
                ch.conversation_id,
                c.name as conversation_name,
                ch.role,
                ch.timestamp,
                ch.content AS full_content,
                similarity(ch.content::text, %s) as sim_score,
                ts_rank(ch.search_vector, plainto_tsquery('english', %s)) as rank,
                cs.total_messages,
                cs.last_activity
            FROM chat_history ch
            INNER JOIN conversations c ON c.id = ch.conversation_id
            INNER JOIN conversation_stats cs ON cs.conversation_id = c.id
            WHERE {" AND ".join(where_clauses)}
            ORDER BY sim_score DESC, rank DESC
            LIMIT %s
        """

        cursor.execute(sql, params + [query, query, limit])
        return cursor.fetchall()

    def search_messages(
        self,
        query: str,
        limit: int = 50,
        role: str = None,
        snippet_type: str = None,
        conversation_id: str = None,
        date_from: str = None,
        date_to: str = None
    ) -> List[Dict]:
        """
        Search message content and return matching messages with context.
        Returns message-level matches with snippets, not just conversation cards.

        Uses PostgreSQL ts_headline for contextual snippets and ts_rank for relevance.

        Args:
            query: Search query string
            limit: Maximum number of results (default: 50)
            role: Filter by role ('user' or 'assistant', optional)
            snippet_type: Filter by snippet type ('code' or 'prose', optional)
            conversation_id: Filter by specific conversation UUID (optional)
            date_from: Filter by date range start, ISO 8601 format (optional)
            date_to: Filter by date range end, ISO 8601 format (optional)
        """
        cursor = self.pg_conn.cursor(cursor_factory=RealDictCursor)

        try:
            # UX-SEARCH-007: Capture query interpretation metadata
            # This will be returned to frontend for transparency
            query_interpretation = {
                'original_query': query,
                'normalized_query': None,
                'stopwords_removed': [],
                'tokens_used': [],
                'search_type': 'full_text',  # vs exact, fuzzy, semantic
            }

            # Get PostgreSQL's interpretation of the query
            # plainto_tsquery normalizes, stems, and removes stopwords
            cursor.execute(
                "SELECT plainto_tsquery('english', %s)::text AS normalized",
                [query]
            )
            normalized_result = cursor.fetchone()
            if normalized_result:
                query_interpretation['normalized_query'] = normalized_result['normalized']
                # Extract tokens from normalized query (format: 'token1' & 'token2')
                import re
                tokens = re.findall(r"'([^']+)'", normalized_result['normalized'])
                query_interpretation['tokens_used'] = tokens

                # Detect stopwords by comparing original vs normalized
                original_words = set(query.lower().split())
                normalized_words = set(tokens)
                stopwords = original_words - normalized_words
                query_interpretation['stopwords_removed'] = list(stopwords)

            # Build dynamic WHERE clause based on filters
            where_clauses = ["ch.search_vector @@ plainto_tsquery('english', %s)"]
            params = [query, query]  # query used twice (rank + where)

            # Add optional filters
            if role:
                where_clauses.append("ch.role = %s")
                params.append(role)

            if conversation_id:
                where_clauses.append("c.conversation_id = %s")
                params.append(conversation_id)

            if date_from:
                where_clauses.append("ch.timestamp >= %s")
                params.append(date_from)

            if date_to:
                where_clauses.append("ch.timestamp <= %s")
                params.append(date_to)

            where_clause = " AND ".join(where_clauses)
            params.append(limit)

            cursor.execute(
                f"""
                WITH conversation_stats AS (
                    SELECT
                        conversation_id,
                        COUNT(*) as total_messages,
                        MAX(timestamp) as last_activity
                    FROM chat_history
                    GROUP BY conversation_id
                )
                SELECT
                    c.conversation_id,
                    c.name AS conversation_name,
                    ch.id AS message_id,
                    ch.role,
                    ch.timestamp,
                    ch.content AS full_content,
                    ts_rank(ch.search_vector, plainto_tsquery('english', %s)) AS rank,
                    cs.total_messages,
                    cs.last_activity
                FROM chat_history ch
                INNER JOIN conversations c ON c.id = ch.conversation_id
                INNER JOIN conversation_stats cs ON cs.conversation_id = c.id
                WHERE {where_clause}
                ORDER BY rank DESC, ch.timestamp DESC
                LIMIT %s
                """,
                params
            )

            results = [dict(row) for row in cursor.fetchall()]

            # MODERN UX: Fuzzy search fallback + "did you mean" suggestion
            did_you_mean = None
            search_type = 'exact'

            # If no exact results, try fuzzy search
            if len(results) == 0:
                # Get "did you mean" suggestion
                did_you_mean = self._get_did_you_mean_suggestion(cursor, query)

                # Try fuzzy search
                fuzzy_results = self._fuzzy_search_messages(
                    cursor, query, limit, role, snippet_type,
                    conversation_id, date_from, date_to
                )

                if fuzzy_results:
                    results = [dict(row) for row in fuzzy_results]
                    search_type = 'fuzzy'
                else:
                    search_type = 'none'

            # Import enforcement module
            import re
            import logging
            from snippet_extraction import (
                extract_snippet_or_fail,
                extract_snippet_best_effort,
                classify_snippet_type,
                SnippetExtractionError
            )

            logger = logging.getLogger(__name__)

            def highlight_terms(text: str, query: str) -> str:
                """Apply <mark> tags to matching terms in text."""
                # Case-insensitive replacement, preserve original case
                pattern = re.escape(query)
                return re.sub(f'({pattern})', r'<mark>\1</mark>', text, flags=re.IGNORECASE)

            # Process results and apply post-DB filters
            filtered_results = []

            for result in results:
                result['timestamp'] = result['timestamp'].isoformat() if result['timestamp'] else None
                result['last_activity'] = result['last_activity'].isoformat() if result.get('last_activity') else None
                result['message_id'] = str(result['message_id'])
                result['rank'] = float(result['rank'])
                result['total_messages'] = int(result.get('total_messages', 0))

                # NORMALIZE CONTENT AT BOUNDARY - will raise if invalid
                # This is the ONLY way content enters downstream logic
                try:
                    full_content = self.normalize_message_content(result.get('full_content'))
                except RuntimeError as e:
                    logger.error(
                        f"DATA NORMALIZATION FAILURE: {e}",
                        extra={
                            "message_id": result.get('message_id'),
                            "conversation_id": result.get('conversation_id'),
                            "raw_type": type(result.get('full_content')),
                            "error": str(e),
                        }
                    )
                    # Re-raise - this is a data integrity violation
                    raise ValueError(f"Message content normalization failed: {e}")

                # Classify content type (now guaranteed to be non-empty string)
                detected_snippet_type = classify_snippet_type(full_content)
                result['snippet_type'] = detected_snippet_type

                # Apply snippet_type filter if specified (post-DB filter)
                # This is done after DB query because snippet_type is determined by content analysis
                if snippet_type and detected_snippet_type != snippet_type:
                    # Skip this result - doesn't match requested type
                    continue

                # UX-FIRST BEST-EFFORT EXTRACTION (ChatGPT FIX 1-4)
                # NEVER throws exceptions for match ambiguity
                try:
                    snippet_data = extract_snippet_best_effort(
                        content=full_content,
                        query=query,
                        context_lines=3
                    )
                except SnippetExtractionError as e:
                    # Only data integrity violations reach here
                    logger.error(
                        f"DATA INTEGRITY VIOLATION: {e}",
                        extra={
                            "message_id": result.get('message_id'),
                            "conversation_id": result.get('conversation_id'),
                            "query": query,
                            "content_type": type(full_content),
                            "content_preview": str(full_content)[:200],
                            "error": str(e),
                        }
                    )
                    # Re-raise as HTTP error - this indicates a boundary violation
                    raise ValueError(f"Data integrity violation in search: {e}")

                # Apply highlighting to the snippet (backward compatibility)
                snippet_with_highlights = highlight_terms(snippet_data['snippet'], query)
                result['snippet'] = snippet_with_highlights

                # Sourcegraph-style structured context with highlighting
                result['context_before'] = [highlight_terms(line, query) for line in snippet_data['context_before']]
                result['matched_lines'] = [highlight_terms(line, query) for line in snippet_data['matched_lines']]
                result['context_after'] = [highlight_terms(line, query) for line in snippet_data['context_after']]

                # Metadata
                result['match_line'] = snippet_data['match_line']
                result['start_line'] = snippet_data['start_line']
                result['end_line'] = snippet_data['end_line']
                result['match_count'] = snippet_data['match_count']
                result['match_positions'] = snippet_data['match_positions']  # Character offsets

                # UX metadata for match confidence and explanation
                result['match_type'] = snippet_data.get('match_type', 'exact')
                result['snippet_confidence'] = snippet_data.get('snippet_confidence', 'high')
                result['snippet_note'] = snippet_data.get('snippet_note')

                # Remove full_content from response
                result.pop('full_content', None)

                # Normalize role
                role = result.get('role', 'unknown')
                if role == 'unknown' or not role:
                    # Try to infer from content
                    snippet_text = snippet_data['snippet']
                    if snippet_text.startswith('```') or 'def ' in snippet_text or 'class ' in snippet_text:
                        result['role'] = 'assistant'  # Likely code response
                    else:
                        result['role'] = 'user'  # Default to user
                else:
                    result['role'] = role

                # Add to filtered results
                filtered_results.append(result)

            # UX-SEARCH-007: Return query interpretation metadata with results
            # This allows frontend to explain search behavior to users
            # MODERN UX: Include fuzzy search metadata
            return {
                'results': filtered_results,
                'query_interpretation': query_interpretation,
                'result_count': len(filtered_results),
                'did_you_mean': did_you_mean,  # NEW: Typo suggestion
                'search_type': search_type,     # NEW: exact|fuzzy|none
            }

        except Exception as e:
            # Rollback transaction on error
            self.pg_conn.rollback()
            raise e

        except Exception as e:
            # Rollback transaction on error to prevent "transaction aborted" state
            self.pg_conn.rollback()
            raise e

        finally:
            cursor.close()

    def get_conversation(self, conversation_id: str) -> Optional[Dict]:
        """Get full conversation data with caching."""
        # Check cache
        cache_key = self._get_cache_key("full_conversation", conversation_id)
        cached = self._cache_get(cache_key)
        if cached:
            print(f"✅ Conversation from cache")
            return cached

        cursor = self.pg_conn.cursor(cursor_factory=RealDictCursor)

        try:
            # Get conversation metadata
            cursor.execute(
                "SELECT * FROM conversations WHERE conversation_id = %s",
                (conversation_id,)
            )
            conv = cursor.fetchone()

            if not conv:
                return None

            conv = dict(conv)
            conv['id'] = str(conv['id'])

            # Get messages
            cursor.execute(
                """
                SELECT message_index, role, content, timestamp
                FROM chat_history
                WHERE conversation_id = %s
                ORDER BY message_index
                """,
                (conv['id'],)
            )
            conv['messages'] = [dict(row) for row in cursor.fetchall()]

            # Get tool states
            cursor.execute(
                """
                SELECT tool_use_id, request_id, phase, result
                FROM tool_use_states
                WHERE conversation_id = %s
                """,
                (conv['id'],)
            )
            conv['tool_states'] = {row['tool_use_id']: dict(row) for row in cursor.fetchall()}

            # Cache full conversation
            self._cache_set(cache_key, conv)

            return conv

        finally:
            cursor.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        cursor = self.pg_conn.cursor(cursor_factory=RealDictCursor)

        try:
            stats = {}

            # Total conversations
            cursor.execute("SELECT COUNT(*) as count FROM conversations")
            stats['total_conversations'] = cursor.fetchone()['count']

            # Total messages
            cursor.execute("SELECT COUNT(*) as count FROM chat_history")
            stats['total_messages'] = cursor.fetchone()['count']

            # Total tool states
            cursor.execute("SELECT COUNT(*) as count FROM tool_use_states")
            stats['total_tool_states'] = cursor.fetchone()['count']

            # Duplicate messages
            cursor.execute("SELECT COUNT(*) as count FROM duplicate_messages")
            stats['duplicate_message_groups'] = cursor.fetchone()['count']

            # Duplicate tool states
            cursor.execute("SELECT COUNT(*) as count FROM duplicate_tool_states")
            stats['duplicate_tool_state_groups'] = cursor.fetchone()['count']

            # Total storage
            cursor.execute(
                "SELECT SUM(file_size_mb) as total FROM conversations"
            )
            stats['total_storage_mb'] = float(cursor.fetchone()['total'] or 0)

            # Redis cache stats
            redis_info = self.redis_client.info('stats')
            stats['redis_keys'] = self.redis_client.dbsize()
            stats['redis_hits'] = redis_info.get('keyspace_hits', 0)
            stats['redis_misses'] = redis_info.get('keyspace_misses', 0)

            return stats

        finally:
            cursor.close()

    def clear_cache(self):
        """Clear all Redis cache."""
        self._cache_delete("augment:*")
        print("✅ Cache cleared")


def main():
    """CLI interface for conversation manager."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Augment Conversation Data Manager - Redis + PostgreSQL with deduplication"
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Import command
    import_parser = subparsers.add_parser('import', help='Import conversation export')
    import_parser.add_argument('file', help='Path to Augment export JSON file')

    # Search command
    search_parser = subparsers.add_parser('search', help='Search conversations')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--limit', type=int, default=10, help='Max results')

    # Get command
    get_parser = subparsers.add_parser('get', help='Get conversation by ID')
    get_parser.add_argument('conversation_id', help='Conversation ID')
    get_parser.add_argument('--output', help='Output file (JSON)')

    # Stats command
    subparsers.add_parser('stats', help='Show database statistics')

    # Clear cache command
    subparsers.add_parser('clear-cache', help='Clear Redis cache')

    # Database connection args
    parser.add_argument('--pg-host', default='localhost', help='PostgreSQL host')
    parser.add_argument('--pg-port', type=int, default=5432, help='PostgreSQL port')
    parser.add_argument('--pg-database', default='augment_conversations', help='PostgreSQL database')
    parser.add_argument('--pg-user', default='marketplace_user', help='PostgreSQL user')
    parser.add_argument('--pg-password', default='marketplace_pass', help='PostgreSQL password')
    parser.add_argument('--redis-host', default='localhost', help='Redis host')
    parser.add_argument('--redis-port', type=int, default=6379, help='Redis port')
    parser.add_argument('--redis-db', type=int, default=0, help='Redis database')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Initialize manager
    manager = ConversationManager(
        pg_host=args.pg_host,
        pg_port=args.pg_port,
        pg_database=args.pg_database,
        pg_user=args.pg_user,
        pg_password=args.pg_password,
        redis_host=args.redis_host,
        redis_port=args.redis_port,
        redis_db=args.redis_db
    )

    # Execute command
    if args.command == 'import':
        result = manager.import_conversation(args.file)
        print(f"\n📊 Import Result:")
        print(f"   Conversation ID: {result['conversation_id']}")
        print(f"   Is Duplicate: {result['is_duplicate']}")
        print(f"   Source: {result['source']}")
        if 'stats' in result:
            print(f"   Stats: {json.dumps(result['stats'], indent=2)}")

    elif args.command == 'search':
        results = manager.search_conversations(args.query, args.limit)
        print(f"\n🔍 Found {len(results)} conversations:")
        for r in results:
            print(f"\n   {r['name']}")
            print(f"   ID: {r['conversation_id']}")
            print(f"   Messages: {r['total_messages']}, Tools: {r['total_tool_states']}")
            print(f"   Last interaction: {r['last_interacted_at']}")

    elif args.command == 'get':
        conv = manager.get_conversation(args.conversation_id)
        if conv:
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(conv, f, indent=2, default=str)
                print(f"✅ Saved to {args.output}")
            else:
                print(json.dumps(conv, indent=2, default=str))
        else:
            print(f"❌ Conversation not found: {args.conversation_id}")

    elif args.command == 'stats':
        stats = manager.get_stats()
        print(f"\n📊 Database Statistics:")
        print(f"   Total conversations: {stats['total_conversations']}")
        print(f"   Total messages: {stats['total_messages']}")
        print(f"   Total tool states: {stats['total_tool_states']}")
        print(f"   Duplicate message groups: {stats['duplicate_message_groups']}")
        print(f"   Duplicate tool state groups: {stats['duplicate_tool_state_groups']}")
        print(f"   Total storage: {stats['total_storage_mb']:.2f} MB")
        print(f"\n📦 Redis Cache:")
        print(f"   Keys: {stats['redis_keys']}")
        print(f"   Hits: {stats['redis_hits']}")
        print(f"   Misses: {stats['redis_misses']}")
        if stats['redis_hits'] + stats['redis_misses'] > 0:
            hit_rate = stats['redis_hits'] / (stats['redis_hits'] + stats['redis_misses']) * 100
            print(f"   Hit rate: {hit_rate:.1f}%")

    elif args.command == 'clear-cache':
        manager.clear_cache()


if __name__ == '__main__':
    main()

