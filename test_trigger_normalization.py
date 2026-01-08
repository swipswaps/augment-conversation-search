#!/usr/bin/env python3
"""
Test that trigger normalization works on new inserts
- Insert a message with mixed case and extra whitespace
- Verify search_vector is normalized
- Verify search works with different query variations
"""

import sys
from conversation_manager import ConversationManager
import uuid
import json

cm = ConversationManager()
cursor = cm.pg_conn.cursor()

try:
    # Create test message with mixed case and extra whitespace
    test_id = uuid.uuid4()
    test_content = {
        "response_text": "This   is  a   TEST   MESSAGE   with   EXTRA    whitespace"
    }
    
    print("="*60)
    print("TEST: Trigger Normalization on New Insert")
    print("="*60)
    print(f"\nTest message ID: {test_id}")
    print(f"Original text: '{test_content['response_text']}'")
    print(f"Expected normalized: 'this is a test message with extra whitespace'")
    
    # Insert test message (conversation_id NULL to avoid foreign key constraint)
    cursor.execute("""
        INSERT INTO chat_history (id, conversation_id, message_index, role, content, content_hash)
        VALUES (%s::uuid, NULL, %s, %s, %s, %s)
    """, (
        str(test_id),
        1,
        'assistant',
        json.dumps(test_content),
        f'test_hash_{test_id}'
    ))
    
    cm.pg_conn.commit()
    print("\n✅ Test message inserted")
    
    # Retrieve the search_vector
    cursor.execute("""
        SELECT
            content->>'response_text' AS original_text,
            search_vector::text AS search_vector
        FROM chat_history
        WHERE id = %s::uuid
    """, (str(test_id),))
    
    result = cursor.fetchone()
    original_text, search_vector = result
    
    print(f"\nOriginal text: '{original_text}'")
    print(f"Search vector: {search_vector[:100]}...")
    
    # Test search with different variations
    test_queries = [
        "TEST",           # Uppercase
        "test",           # Lowercase
        "  test  ",       # With whitespace
        "message",        # Different word
        "extra whitespace"  # Multi-word
    ]
    
    print("\n" + "="*60)
    print("SEARCH TESTS")
    print("="*60)
    
    all_passed = True
    for query in test_queries:
        cursor.execute("""
            SELECT id
            FROM chat_history
            WHERE id = %s::uuid
            AND search_vector @@ plainto_tsquery('english', %s)
        """, (str(test_id), query))
        
        found = cursor.fetchone() is not None
        status = "✅ FOUND" if found else "❌ NOT FOUND"
        print(f"{status}: Query '{query}'")
        
        if not found:
            all_passed = False
    
    # Clean up test message
    cursor.execute("DELETE FROM chat_history WHERE id = %s::uuid", (str(test_id),))
    cm.pg_conn.commit()
    print("\n✅ Test message cleaned up")
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ ALL TESTS PASSED - Trigger normalization working correctly")
    else:
        print("❌ SOME TESTS FAILED - Trigger normalization may have issues")
    print("="*60)
    
    cursor.close()
    
except Exception as e:
    cm.pg_conn.rollback()
    print(f"\n❌ TEST FAILED: {e}")
    raise

