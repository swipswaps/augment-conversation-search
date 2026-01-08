#!/usr/bin/env python3
"""
Test script for Augment Conversation Data Manager
Verifies all functionality works correctly.
"""

import json
import os
import sys
import tempfile
from datetime import datetime

from conversation_manager import ConversationManager


def create_test_export():
    """Create a minimal test export file."""
    test_data = {
        "version": "1.0.0",
        "exportedAt": datetime.now().isoformat(),
        "conversation": {
            "id": "test-conversation-001",
            "name": "Test Conversation",
            "createdAtIso": "2026-01-01T00:00:00Z",
            "lastInteractedAtIso": "2026-01-05T00:00:00Z",
            "personaType": "agent",
            "chatHistory": [
                {
                    "role": "user",
                    "content": "Hello, this is a test message",
                    "timestamp": "2026-01-01T00:00:00Z"
                },
                {
                    "role": "assistant",
                    "content": "This is a test response",
                    "timestamp": "2026-01-01T00:00:01Z"
                }
            ],
            "toolUseStates": {
                "tool-001": {
                    "requestId": "req-001",
                    "phase": 1,
                    "result": {"status": "success"}
                }
            },
            "draftActiveContextIds": [],
            "extraData": {}
        }
    }
    
    # Create temp file
    fd, path = tempfile.mkstemp(suffix='.json')
    with os.fdopen(fd, 'w') as f:
        json.dump(test_data, f)
    
    return path


def test_import(manager):
    """Test conversation import."""
    print("\n🧪 Test 1: Import Conversation")
    
    test_file = create_test_export()
    
    try:
        result = manager.import_conversation(test_file)
        
        assert result['is_duplicate'] == False, "First import should not be duplicate"
        assert result['source'] == 'new', "First import should be from new source"
        
        print("✅ Test 1 passed: Import successful")
        
        return result['conversation_id']
        
    finally:
        os.unlink(test_file)


def test_duplicate_detection(manager):
    """Test duplicate detection."""
    print("\n🧪 Test 2: Duplicate Detection")
    
    test_file = create_test_export()
    
    try:
        # Import same file twice
        result1 = manager.import_conversation(test_file)
        result2 = manager.import_conversation(test_file)
        
        assert result2['is_duplicate'] == True, "Second import should be duplicate"
        assert result1['conversation_id'] == result2['conversation_id'], "Should return same conversation ID"
        
        print("✅ Test 2 passed: Duplicate detection works")
        
    finally:
        os.unlink(test_file)


def test_search(manager):
    """Test search functionality."""
    print("\n🧪 Test 3: Search")
    
    results = manager.search_conversations("Test")
    
    assert len(results) > 0, "Should find test conversations"
    assert any('Test' in r['name'] for r in results), "Should find conversations with 'Test' in name"
    
    print(f"✅ Test 3 passed: Found {len(results)} conversations")


def test_get_conversation(manager, conversation_id):
    """Test getting full conversation."""
    print("\n🧪 Test 4: Get Conversation")
    
    conv = manager.get_conversation("test-conversation-001")
    
    assert conv is not None, "Should find conversation"
    assert conv['conversation_id'] == "test-conversation-001", "Should return correct conversation"
    assert 'messages' in conv, "Should include messages"
    assert 'tool_states' in conv, "Should include tool states"
    
    print("✅ Test 4 passed: Retrieved full conversation")


def test_stats(manager):
    """Test statistics."""
    print("\n🧪 Test 5: Statistics")
    
    stats = manager.get_stats()
    
    assert 'total_conversations' in stats, "Should include total conversations"
    assert 'total_messages' in stats, "Should include total messages"
    assert 'redis_keys' in stats, "Should include Redis stats"
    
    print("✅ Test 5 passed: Statistics retrieved")
    print(f"   Conversations: {stats['total_conversations']}")
    print(f"   Messages: {stats['total_messages']}")
    print(f"   Redis keys: {stats['redis_keys']}")


def test_cache(manager):
    """Test caching."""
    print("\n🧪 Test 6: Caching")
    
    # First search (cache miss)
    results1 = manager.search_conversations("Test")
    
    # Second search (cache hit)
    results2 = manager.search_conversations("Test")
    
    assert results1 == results2, "Cached results should match"
    
    # Clear cache
    manager.clear_cache()
    
    print("✅ Test 6 passed: Caching works")


def main():
    """Run all tests."""
    print("🧪 Testing Augment Conversation Data Manager")
    print("=" * 60)
    
    # Initialize manager
    try:
        manager = ConversationManager()
    except Exception as e:
        print(f"❌ Failed to connect to services: {e}")
        print("\n💡 Make sure PostgreSQL and Redis are running:")
        print("   docker-compose -f docker-compose-conversation-manager.yml up -d")
        sys.exit(1)
    
    try:
        # Run tests
        conversation_id = test_import(manager)
        test_duplicate_detection(manager)
        test_search(manager)
        test_get_conversation(manager, conversation_id)
        test_stats(manager)
        test_cache(manager)
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

