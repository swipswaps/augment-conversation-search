#!/usr/bin/env python3
"""
Augment Conversation Manager - Web API Server
Flask REST API to serve conversation data from PostgreSQL/Redis
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import json
import os
import time
from psycopg2.extras import RealDictCursor

from conversation_manager import ConversationManager

app = Flask(__name__, static_folder='web', static_url_path='')
CORS(app)  # Enable CORS for GitHub Pages

# Initialize conversation manager
manager = ConversationManager(
    pg_host=os.getenv('PG_HOST', 'localhost'),
    pg_port=int(os.getenv('PG_PORT', 5432)),
    pg_database=os.getenv('PG_DATABASE', 'augment_conversations'),
    pg_user=os.getenv('PG_USER', 'marketplace_user'),
    pg_password=os.getenv('PG_PASSWORD', 'marketplace_pass'),
    redis_host=os.getenv('REDIS_HOST', 'localhost'),
    redis_port=int(os.getenv('REDIS_PORT', 6379)),
    redis_db=int(os.getenv('REDIS_DB', 0))
)

# ---- STATEFUL QUERY MEMORY (per session) ----
# UX-SEARCH-006: Track previous queries to detect ranking collapse
LAST_QUERY_CACHE = {}

# UX-SEARCH-006: Hard thresholds for UX failure detection
MAX_OVERLAP = 0.90  # 90%+ overlap = fake refinement
MIN_TOP10_CHANGES = 3  # Top-10 must change meaningfully


def analyze_refinement(prev_ids, curr_ids):
    """
    UX-SEARCH-006: Analyze whether query refinement produced meaningful changes.

    Returns dict with:
        - overlap: percentage of results that are identical
        - top10_changes: number of top-10 positions that changed
        - failed: True if refinement is fake (overlap ≥90% AND top-10 barely changed)

    Returns None if no previous query exists.
    """
    if not prev_ids or not curr_ids:
        return None

    # Overall overlap
    overlap = len(set(prev_ids) & set(curr_ids)) / max(len(curr_ids), 1)

    # Top-10 rank movement (how many positions changed)
    top10_changes = sum(
        1 for i, cid in enumerate(curr_ids[:10])
        if i >= len(prev_ids) or prev_ids[i] != cid
    )

    # UX FAILURE: High overlap AND low rank movement
    failed = overlap >= MAX_OVERLAP and top10_changes < MIN_TOP10_CHANGES

    return {
        "overlap": overlap,
        "top10_changes": top10_changes,
        "failed": failed
    }


def explain_query(query):
    """
    UX-SEARCH-007: Explain query interpretation to user.

    Users should not have to guess what the search engine did.
    This returns metadata about stopword removal, stemming, etc.

    Returns:
        dict: Query interpretation metadata
    """
    tokens = query.split()
    stopwords = {"the", "a", "an", "of", "to", "in", "on", "at", "for", "with"}

    removed = [t for t in tokens if t.lower() in stopwords]
    kept = [t for t in tokens if t.lower() not in stopwords]

    return {
        "original": query,
        "tokens": tokens,
        "stopwords_removed": removed,
        "effective_terms": kept,
        "stemming_enabled": True,
        "fuzzy_matching_enabled": True
    }


@app.route('/')
def index():
    """Serve the web UI"""
    response = send_from_directory('web', 'app.html')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/app.js')
def serve_js():
    """Serve JavaScript with no-cache headers"""
    response = send_from_directory('web', 'app.js')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/api/conversations', methods=['GET'])
def list_conversations():
    """List all conversations with pagination"""
    try:
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        cursor = manager.pg_conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT conversation_id, name, created_at, last_interacted_at,
                   total_messages, total_tool_states, file_size_mb
            FROM conversations
            ORDER BY last_interacted_at DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset)
        )
        
        conversations = []
        for row in cursor.fetchall():
            conversations.append({
                'conversation_id': row['conversation_id'],
                'name': row['name'],
                'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                'last_interacted_at': row['last_interacted_at'].isoformat() if row['last_interacted_at'] else None,
                'total_messages': row['total_messages'],
                'total_tool_states': row['total_tool_states'],
                'file_size_mb': float(row['file_size_mb']) if row['file_size_mb'] else 0
            })
        
        cursor.close()
        
        return jsonify({
            'success': True,
            'conversations': conversations,
            'count': len(conversations)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/conversations/<conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    """Get full conversation data"""
    try:
        conv = manager.get_conversation(conversation_id)
        
        if not conv:
            return jsonify({'success': False, 'error': 'Conversation not found'}), 404
        
        # Convert datetime objects to ISO format
        if 'created_at' in conv and conv['created_at']:
            conv['created_at'] = conv['created_at'].isoformat() if hasattr(conv['created_at'], 'isoformat') else conv['created_at']
        if 'last_interacted_at' in conv and conv['last_interacted_at']:
            conv['last_interacted_at'] = conv['last_interacted_at'].isoformat() if hasattr(conv['last_interacted_at'], 'isoformat') else conv['last_interacted_at']
        
        return jsonify({
            'success': True,
            'conversation': conv
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/search', methods=['GET'])
def search_conversations():
    """Search conversations by name"""
    try:
        query = request.args.get('q', '')
        limit = int(request.args.get('limit', 10))

        if not query:
            return jsonify({'success': False, 'error': 'Query parameter required'}), 400

        results = manager.search_conversations(query, limit)

        return jsonify({
            'success': True,
            'results': results,
            'count': len(results)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def enforce_search_response_schema(payload):
    """
    PRF-API-SCHEMA-001: Enforce search response schema contract.

    HARD INVARIANTS:
    - If HTTP 200 is returned, the payload MUST match the search schema
    - No exceptions. No alternate shapes. No "message instead"
    - Every result must have non-empty snippet and snippet_type
    - UX-SEARCH-007: Must include query_interpretation for transparency

    This rule is executable, not documented.
    Violations cause immediate HTTP 500, not silent degradation.
    """
    # VERACITY CHECK 1: Payload is dict
    if not isinstance(payload, dict):
        raise RuntimeError(f"Search response is not a JSON object, got {type(payload)}")

    # VERACITY CHECK 2: Required keys exist
    if "results" not in payload:
        raise RuntimeError(
            f"Invalid search response: missing 'results' key. Keys present: {list(payload.keys())}"
        )

    # VERACITY CHECK 3: Results is a list
    if not isinstance(payload["results"], list):
        raise RuntimeError(f"'results' must be a list, got {type(payload['results'])}")

    # VERACITY CHECK 4: Each result has required fields and non-empty snippet
    for idx, result in enumerate(payload["results"]):
        if not isinstance(result, dict):
            raise RuntimeError(f"Result[{idx}] is not a dict, got {type(result)}")

        if "snippet" not in result:
            raise RuntimeError(f"Result[{idx}] missing 'snippet' field")

        if not result["snippet"] or not isinstance(result["snippet"], str):
            raise RuntimeError(
                f"Result[{idx}] has empty or non-string snippet: {type(result['snippet'])}"
            )

        if "snippet_type" not in result:
            raise RuntimeError(f"Result[{idx}] missing 'snippet_type' field")

        if result["snippet_type"] not in ["code", "prose"]:
            raise RuntimeError(
                f"Result[{idx}] has invalid snippet_type: {result['snippet_type']}"
            )

        # ChatGPT FIX 2: Validate UX metadata fields (REQUIRED)
        if "match_type" not in result:
            raise RuntimeError(f"Result[{idx}] missing 'match_type' field (ChatGPT FIX 2)")

        if result["match_type"] not in ["exact", "fuzzy", "fallback"]:
            raise RuntimeError(
                f"Result[{idx}] has invalid match_type: {result['match_type']}"
            )

        if "snippet_confidence" not in result:
            raise RuntimeError(f"Result[{idx}] missing 'snippet_confidence' field (ChatGPT FIX 2)")

        if result["snippet_confidence"] not in ["high", "medium", "low"]:
            raise RuntimeError(
                f"Result[{idx}] has invalid snippet_confidence: {result['snippet_confidence']}"
            )

        # snippet_note is optional (None allowed)
        if "snippet_note" not in result:
            raise RuntimeError(f"Result[{idx}] missing 'snippet_note' field (ChatGPT FIX 2)")

    # All checks passed
    return payload


@app.route('/api/search/messages', methods=['GET'])
def search_messages():
    """
    Search message content and return matching messages with snippets.

    Query Parameters:
        q (required): Search query string
        limit (optional): Maximum results (default: 50)
        role (optional): Filter by role ('user' or 'assistant')
        type (optional): Filter by snippet type ('code' or 'prose')
        conversation_id (optional): Filter by conversation UUID
        date_from (optional): Filter by date range start (ISO 8601)
        date_to (optional): Filter by date range end (ISO 8601)
    """
    try:
        start_time = time.time()

        query = request.args.get('q', '').strip()
        limit = int(request.args.get('limit', 50))
        session_id = request.remote_addr  # Simple session tracking (replace with real session ID later)

        # Optional filters
        role = request.args.get('role', None)
        snippet_type = request.args.get('type', None)
        conversation_id = request.args.get('conversation_id', None)
        date_from = request.args.get('date_from', None)
        date_to = request.args.get('date_to', None)

        if not query:
            payload = {
                'success': True,
                'results': [],
                'count': 0,
                'ux_status': 'idle'
            }
            return jsonify(enforce_search_response_schema(payload))

        search_response = manager.search_messages(
            query=query,
            limit=limit,
            role=role,
            snippet_type=snippet_type,
            conversation_id=conversation_id,
            date_from=date_from,
            date_to=date_to
        )

        # UX-SEARCH-007: Extract query interpretation metadata
        # search_response is now a dict with 'results' and 'query_interpretation'
        results = search_response.get('results', [])
        query_interpretation = search_response.get('query_interpretation', {})

        # MODERN UX: Extract fuzzy search metadata
        did_you_mean = search_response.get('did_you_mean')
        search_type = search_response.get('search_type', 'exact')

        # UX-SEARCH-006: Analyze refinement quality
        current_ids = [r['message_id'] for r in results]
        prev = LAST_QUERY_CACHE.get(session_id)

        analysis = analyze_refinement(
            prev['ids'] if prev else None,
            current_ids
        )

        ux_status = "ok"
        ux_block = False
        ux_reason = None

        if analysis and analysis['failed']:
            ux_status = "degraded"
            ux_block = True
            ux_reason = (
                f"Refinement failed: {int(analysis['overlap']*100)}% overlap, "
                f"only {analysis['top10_changes']} top-10 changes"
            )

        # Store current query for next comparison
        LAST_QUERY_CACHE[session_id] = {
            'query': query,
            'ids': current_ids
        }

        # UX-SEARCH-007: Explain query interpretation
        query_explanation_meta = explain_query(query)

        elapsed_ms = int((time.time() - start_time) * 1000)

        # UX-NFC-002: HARD BLOCK - Return empty results if UX failed
        if ux_block:
            payload = {
                'success': True,
                'results': [],  # 🔒 HARD BLOCK - no results
                'count': 0,
                'query': query,
                'query_explanation': query_explanation_meta,
                'elapsed_ms': elapsed_ms,
                'ux_status': ux_status,
                'ux_block': ux_block,
                'ux_reason': ux_reason,
                'ux_metrics': analysis,
                'filters': {
                    'role': role,
                    'type': snippet_type,
                    'conversation_id': conversation_id,
                    'date_from': date_from,
                    'date_to': date_to
                }
            }
            return jsonify(enforce_search_response_schema(payload))

        # UX-SEARCH-006: Normal response (UX passed)
        payload = {
            'success': True,
            'results': results,
            'count': len(results),
            'query': query,
            'query_interpretation': query_interpretation,  # Legacy
            'query_explanation': query_explanation_meta,  # UX-SEARCH-007
            'did_you_mean': did_you_mean,  # MODERN UX: Typo suggestion
            'search_type': search_type,     # MODERN UX: exact|fuzzy|none
            'elapsed_ms': elapsed_ms,
            'ux_status': ux_status,
            'ux_block': ux_block,
            'ux_reason': ux_reason,
            'ux_metrics': analysis,  # Contains overlap, top10_changes, failed
            'filters': {
                'role': role,
                'type': snippet_type,
                'conversation_id': conversation_id,
                'date_from': date_from,
                'date_to': date_to
            }
        }

        # ENFORCE SCHEMA - will raise if invalid
        payload = enforce_search_response_schema(payload)

        return jsonify(payload)

    except Exception as e:
        # Rollback any failed transaction to prevent "transaction aborted" errors
        try:
            manager.pg_conn.rollback()
        except:
            pass
        # Schema violations and extraction failures return HTTP 500, not 200
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/autocomplete', methods=['GET'])
def autocomplete():
    """
    Autocomplete endpoint for search suggestions.

    Query Parameters:
        q (required): Partial query string
        limit (optional): Maximum suggestions (default: 10)

    Returns:
        {
            "success": true,
            "suggestions": ["word1", "word2", ...],
            "count": 5
        }
    """
    try:
        query = request.args.get('q', '').strip()
        limit = int(request.args.get('limit', 10))

        if not query or len(query) < 2:
            return jsonify({
                'success': True,
                'suggestions': [],
                'count': 0
            })

        cursor = manager.pg_conn.cursor(cursor_factory=RealDictCursor)

        # Get words similar to query using trigrams
        cursor.execute("""
            SELECT word, similarity(word, %s) as sim
            FROM ts_stat('SELECT search_vector FROM chat_history')
            WHERE similarity(word, %s) > 0.3
            ORDER BY sim DESC
            LIMIT %s
        """, (query, query, limit))

        suggestions = [row['word'] for row in cursor.fetchall()]
        cursor.close()

        return jsonify({
            'success': True,
            'suggestions': suggestions,
            'count': len(suggestions)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get database statistics"""
    try:
        stats = manager.get_stats()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/messages/<conversation_id>', methods=['GET'])
def get_messages(conversation_id):
    """Get messages for a conversation"""
    try:
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        
        cursor = manager.pg_conn.cursor(cursor_factory=RealDictCursor)
        
        # Get conversation ID from conversation_id string
        cursor.execute(
            "SELECT id FROM conversations WHERE conversation_id = %s",
            (conversation_id,)
        )
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            return jsonify({'success': False, 'error': 'Conversation not found'}), 404
        
        db_conv_id = result['id']
        
        # Get messages
        cursor.execute(
            """
            SELECT message_index, role, content, timestamp
            FROM chat_history
            WHERE conversation_id = %s
            ORDER BY message_index
            LIMIT %s OFFSET %s
            """,
            (db_conv_id, limit, offset)
        )
        
        messages = []
        for row in cursor.fetchall():
            messages.append({
                'index': row['message_index'],
                'role': row['role'],
                'content': row['content'],
                'timestamp': row['timestamp'].isoformat() if row['timestamp'] else None
            })
        
        cursor.close()
        
        return jsonify({
            'success': True,
            'messages': messages,
            'count': len(messages)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test PostgreSQL
        cursor = manager.pg_conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        
        # Test Redis
        manager.redis_client.ping()
        
        return jsonify({
            'success': True,
            'postgresql': 'connected',
            'redis': 'connected'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    print("🚀 Starting Augment Conversation Manager API Server")
    print("📊 PostgreSQL: localhost:5432/augment_conversations")
    print("📦 Redis: localhost:6379/0")
    print("🌐 API Server: http://localhost:5001")
    print("🌐 Web UI: http://localhost:5001/")
    
    app.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)
