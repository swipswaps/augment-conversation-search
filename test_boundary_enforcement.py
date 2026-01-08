#!/usr/bin/env python3
"""
Test boundary enforcement for data normalization.

These tests verify that:
1. normalize_message_content() enforces type and emptiness invariants
2. Invalid data cannot bypass the boundary
3. All failure modes are loud and explicit
"""

import sys
import pytest
from conversation_manager import ConversationManager


def test_normalize_message_content_with_dict():
    """Test normalization of JSONB dict from database"""
    manager = ConversationManager()
    
    # Assistant message format
    raw = {
        'response_text': 'This is the actual content',
        'model_id': 'claude-sonnet-4-5',
        'timestamp': '2026-01-07T00:00:00Z'
    }
    result = manager.normalize_message_content(raw)
    assert result == 'This is the actual content'
    assert isinstance(result, str)


def test_normalize_message_content_with_string():
    """Test normalization of plain string"""
    manager = ConversationManager()
    
    raw = "  Plain text content  "
    result = manager.normalize_message_content(raw)
    assert result == 'Plain text content'
    assert isinstance(result, str)


def test_normalize_message_content_rejects_none():
    """Test that None is rejected loudly"""
    manager = ConversationManager()
    
    with pytest.raises(RuntimeError, match="Message content is None"):
        manager.normalize_message_content(None)


def test_normalize_message_content_rejects_empty_string():
    """Test that empty strings are rejected"""
    manager = ConversationManager()
    
    with pytest.raises(RuntimeError, match="Normalized message content is empty"):
        manager.normalize_message_content("")
    
    with pytest.raises(RuntimeError, match="Normalized message content is empty"):
        manager.normalize_message_content("   ")


def test_normalize_message_content_rejects_empty_dict():
    """Test that dicts with no text fields are rejected"""
    manager = ConversationManager()
    
    raw = {'model_id': 'test', 'timestamp': '2026-01-07'}
    with pytest.raises(RuntimeError, match="Normalized message content is empty"):
        manager.normalize_message_content(raw)


def test_normalize_message_content_rejects_invalid_type():
    """Test that unsupported types are rejected"""
    manager = ConversationManager()
    
    with pytest.raises(RuntimeError, match="Unsupported content type"):
        manager.normalize_message_content(12345)
    
    with pytest.raises(RuntimeError, match="Unsupported content type"):
        manager.normalize_message_content([1, 2, 3])


def test_normalize_message_content_tries_multiple_keys():
    """Test that normalization tries multiple dict keys"""
    manager = ConversationManager()
    
    # response_text
    assert manager.normalize_message_content({'response_text': 'A'}) == 'A'
    
    # content (fallback)
    assert manager.normalize_message_content({'content': 'B'}) == 'B'
    
    # text (fallback)
    assert manager.normalize_message_content({'text': 'C'}) == 'C'
    
    # response_text takes precedence
    result = manager.normalize_message_content({
        'response_text': 'A',
        'content': 'B',
        'text': 'C'
    })
    assert result == 'A'


if __name__ == '__main__':
    print("Running boundary enforcement tests...")
    print("")
    
    # Run tests manually without pytest
    manager = ConversationManager()
    
    tests = [
        ("Dict with response_text", lambda: test_normalize_message_content_with_dict()),
        ("Plain string", lambda: test_normalize_message_content_with_string()),
        ("Rejects None", lambda: test_normalize_message_content_rejects_none()),
        ("Rejects empty string", lambda: test_normalize_message_content_rejects_empty_string()),
        ("Rejects empty dict", lambda: test_normalize_message_content_rejects_empty_dict()),
        ("Rejects invalid type", lambda: test_normalize_message_content_rejects_invalid_type()),
        ("Tries multiple keys", lambda: test_normalize_message_content_tries_multiple_keys()),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            print(f"✅ PASS: {name}")
            passed += 1
        except Exception as e:
            print(f"❌ FAIL: {name}")
            print(f"   Error: {e}")
            failed += 1
    
    print("")
    print(f"Results: {passed} passed, {failed} failed")
    
    sys.exit(0 if failed == 0 else 1)

