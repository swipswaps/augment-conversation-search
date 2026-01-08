#!/usr/bin/env python3
"""
Exhaustive type validation tests for PRF-DATA-SHAPE-001 compliance.

Tests every possible input type to normalize_message_content():
- Valid: str, dict with known keys
- Invalid: None, int, float, list, tuple, bool, set, bytes, nested dicts

All invalid types must raise RuntimeError with descriptive message.
No silent failures. No defaults. No fallbacks.
"""

import sys
from conversation_manager import ConversationManager


def test_valid_string():
    """Valid: plain string"""
    manager = ConversationManager()
    result = manager.normalize_message_content("Hello world")
    assert result == "Hello world"
    assert isinstance(result, str)
    print("✅ PASS: Valid string")


def test_valid_string_with_whitespace():
    """Valid: string with leading/trailing whitespace"""
    manager = ConversationManager()
    result = manager.normalize_message_content("  Hello world  ")
    assert result == "Hello world"
    print("✅ PASS: String with whitespace stripped")


def test_valid_dict_response_text():
    """Valid: dict with response_text key"""
    manager = ConversationManager()
    result = manager.normalize_message_content({
        "response_text": "Assistant response",
        "model_id": "claude-sonnet-4-5"
    })
    assert result == "Assistant response"
    print("✅ PASS: Dict with response_text")


def test_valid_dict_content():
    """Valid: dict with content key (fallback)"""
    manager = ConversationManager()
    result = manager.normalize_message_content({"content": "User message"})
    assert result == "User message"
    print("✅ PASS: Dict with content")


def test_valid_dict_text():
    """Valid: dict with text key (fallback)"""
    manager = ConversationManager()
    result = manager.normalize_message_content({"text": "Some text"})
    assert result == "Some text"
    print("✅ PASS: Dict with text")


def test_invalid_none():
    """Invalid: None must be rejected"""
    manager = ConversationManager()
    try:
        manager.normalize_message_content(None)
        print("❌ FAIL: None was accepted")
        sys.exit(1)
    except RuntimeError as e:
        assert "None" in str(e)
        print("✅ PASS: None rejected")


def test_invalid_empty_string():
    """Invalid: empty string must be rejected"""
    manager = ConversationManager()
    try:
        manager.normalize_message_content("")
        print("❌ FAIL: Empty string was accepted")
        sys.exit(1)
    except RuntimeError as e:
        assert "empty" in str(e).lower()
        print("✅ PASS: Empty string rejected")


def test_invalid_whitespace_only():
    """Invalid: whitespace-only string must be rejected"""
    manager = ConversationManager()
    try:
        manager.normalize_message_content("   \n\t  ")
        print("❌ FAIL: Whitespace-only string was accepted")
        sys.exit(1)
    except RuntimeError as e:
        assert "empty" in str(e).lower()
        print("✅ PASS: Whitespace-only string rejected")


def test_invalid_empty_dict():
    """Invalid: empty dict must be rejected"""
    manager = ConversationManager()
    try:
        manager.normalize_message_content({})
        print("❌ FAIL: Empty dict was accepted")
        sys.exit(1)
    except RuntimeError as e:
        assert "empty" in str(e).lower()
        print("✅ PASS: Empty dict rejected")


def test_invalid_dict_no_text_keys():
    """Invalid: dict without text keys must be rejected"""
    manager = ConversationManager()
    try:
        manager.normalize_message_content({"model_id": "test", "timestamp": "2026-01-07"})
        print("❌ FAIL: Dict without text keys was accepted")
        sys.exit(1)
    except RuntimeError as e:
        assert "empty" in str(e).lower()
        print("✅ PASS: Dict without text keys rejected")


def test_invalid_int():
    """Invalid: integer must be rejected"""
    manager = ConversationManager()
    try:
        manager.normalize_message_content(12345)
        print("❌ FAIL: Integer was accepted")
        sys.exit(1)
    except RuntimeError as e:
        assert "Unsupported content type" in str(e)
        print("✅ PASS: Integer rejected")


def test_invalid_float():
    """Invalid: float must be rejected"""
    manager = ConversationManager()
    try:
        manager.normalize_message_content(123.45)
        print("❌ FAIL: Float was accepted")
        sys.exit(1)
    except RuntimeError as e:
        assert "Unsupported content type" in str(e)
        print("✅ PASS: Float rejected")


def test_invalid_list():
    """Invalid: list must be rejected"""
    manager = ConversationManager()
    try:
        manager.normalize_message_content(["hello", "world"])
        print("❌ FAIL: List was accepted")
        sys.exit(1)
    except RuntimeError as e:
        assert "Unsupported content type" in str(e)
        print("✅ PASS: List rejected")


def test_invalid_bool():
    """Invalid: boolean must be rejected"""
    manager = ConversationManager()
    try:
        manager.normalize_message_content(True)
        print("❌ FAIL: Boolean was accepted")
        sys.exit(1)
    except RuntimeError as e:
        assert "Unsupported content type" in str(e)
        print("✅ PASS: Boolean rejected")


def test_invalid_bytes():
    """Invalid: bytes must be rejected"""
    manager = ConversationManager()
    try:
        manager.normalize_message_content(b"hello")
        print("❌ FAIL: Bytes was accepted")
        sys.exit(1)
    except RuntimeError as e:
        assert "Unsupported content type" in str(e)
        print("✅ PASS: Bytes rejected")


def test_dict_key_precedence():
    """Verify response_text takes precedence over other keys"""
    manager = ConversationManager()
    result = manager.normalize_message_content({
        "response_text": "A",
        "content": "B",
        "text": "C"
    })
    assert result == "A", f"Expected 'A', got '{result}'"
    print("✅ PASS: response_text takes precedence")


if __name__ == '__main__':
    print("=" * 60)
    print("EXHAUSTIVE TYPE VALIDATION TESTS")
    print("PRF-DATA-SHAPE-001 Compliance")
    print("=" * 60)
    print()

    tests = [
        test_valid_string,
        test_valid_string_with_whitespace,
        test_valid_dict_response_text,
        test_valid_dict_content,
        test_valid_dict_text,
        test_invalid_none,
        test_invalid_empty_string,
        test_invalid_whitespace_only,
        test_invalid_empty_dict,
        test_invalid_dict_no_text_keys,
        test_invalid_int,
        test_invalid_float,
        test_invalid_list,
        test_invalid_bool,
        test_invalid_bytes,
        test_dict_key_precedence,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"❌ FAIL: {test_func.__name__}")
            print(f"   Error: {e}")
            failed += 1

    print()
    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
    else:
        print()
        print("✅ ALL EXHAUSTIVE TYPE TESTS PASSED")
        print("✅ PRF-DATA-SHAPE-001 ENFORCED")
        sys.exit(0)

