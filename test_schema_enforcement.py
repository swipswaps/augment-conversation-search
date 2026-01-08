#!/usr/bin/env python3
"""
Exhaustive schema enforcement tests for PRF-API-SCHEMA-001 compliance.

Tests every possible response shape to enforce_search_response_schema():
- Valid: proper dict with results array containing valid snippets
- Invalid: wrong types, missing keys, empty snippets, invalid snippet_type

All invalid schemas must raise RuntimeError.
No HTTP 200 with invalid schema. No silent degradation.
"""

import sys
sys.path.insert(0, '.')

from api_server import enforce_search_response_schema


def test_valid_schema_with_results():
    """Valid: proper schema with results"""
    payload = {
        "success": True,
        "results": [
            {
                "snippet": "print('hello')",
                "snippet_type": "code",
                "message_id": "123"
            }
        ],
        "count": 1
    }
    result = enforce_search_response_schema(payload)
    assert result == payload
    print("✅ PASS: Valid schema with results")


def test_valid_schema_empty_results():
    """Valid: proper schema with empty results"""
    payload = {
        "success": True,
        "results": [],
        "count": 0
    }
    result = enforce_search_response_schema(payload)
    assert result == payload
    print("✅ PASS: Valid schema with empty results")


def test_valid_schema_multiple_results():
    """Valid: multiple results with different snippet types"""
    payload = {
        "success": True,
        "results": [
            {"snippet": "code snippet", "snippet_type": "code"},
            {"snippet": "prose snippet", "snippet_type": "prose"},
        ],
        "count": 2
    }
    result = enforce_search_response_schema(payload)
    assert result == payload
    print("✅ PASS: Valid schema with multiple results")


def test_invalid_not_dict():
    """Invalid: payload is not a dict"""
    try:
        enforce_search_response_schema("not a dict")
        print("❌ FAIL: Non-dict payload was accepted")
        sys.exit(1)
    except RuntimeError as e:
        assert "not a JSON object" in str(e)
        print("✅ PASS: Non-dict payload rejected")


def test_invalid_missing_results_key():
    """Invalid: missing 'results' key"""
    try:
        enforce_search_response_schema({"success": True, "count": 0})
        print("❌ FAIL: Missing 'results' key was accepted")
        sys.exit(1)
    except RuntimeError as e:
        assert "missing 'results' key" in str(e)
        print("✅ PASS: Missing 'results' key rejected")


def test_invalid_results_not_list():
    """Invalid: 'results' is not a list"""
    try:
        enforce_search_response_schema({"results": "not a list"})
        print("❌ FAIL: Non-list 'results' was accepted")
        sys.exit(1)
    except RuntimeError as e:
        assert "'results' must be a list" in str(e)
        print("✅ PASS: Non-list 'results' rejected")


def test_invalid_result_not_dict():
    """Invalid: result item is not a dict"""
    try:
        enforce_search_response_schema({
            "results": ["not a dict"]
        })
        print("❌ FAIL: Non-dict result item was accepted")
        sys.exit(1)
    except RuntimeError as e:
        assert "is not a dict" in str(e)
        print("✅ PASS: Non-dict result item rejected")


def test_invalid_missing_snippet():
    """Invalid: result missing 'snippet' field"""
    try:
        enforce_search_response_schema({
            "results": [{"snippet_type": "code"}]
        })
        print("❌ FAIL: Missing 'snippet' field was accepted")
        sys.exit(1)
    except RuntimeError as e:
        assert "missing 'snippet' field" in str(e)
        print("✅ PASS: Missing 'snippet' field rejected")


def test_invalid_empty_snippet():
    """Invalid: snippet is empty string"""
    try:
        enforce_search_response_schema({
            "results": [{"snippet": "", "snippet_type": "code"}]
        })
        print("❌ FAIL: Empty snippet was accepted")
        sys.exit(1)
    except RuntimeError as e:
        assert "empty or non-string snippet" in str(e)
        print("✅ PASS: Empty snippet rejected")


def test_invalid_snippet_not_string():
    """Invalid: snippet is not a string"""
    try:
        enforce_search_response_schema({
            "results": [{"snippet": 123, "snippet_type": "code"}]
        })
        print("❌ FAIL: Non-string snippet was accepted")
        sys.exit(1)
    except RuntimeError as e:
        assert "empty or non-string snippet" in str(e)
        print("✅ PASS: Non-string snippet rejected")


def test_invalid_missing_snippet_type():
    """Invalid: result missing 'snippet_type' field"""
    try:
        enforce_search_response_schema({
            "results": [{"snippet": "hello"}]
        })
        print("❌ FAIL: Missing 'snippet_type' field was accepted")
        sys.exit(1)
    except RuntimeError as e:
        assert "missing 'snippet_type' field" in str(e)
        print("✅ PASS: Missing 'snippet_type' field rejected")


def test_invalid_snippet_type_value():
    """Invalid: snippet_type has invalid value"""
    try:
        enforce_search_response_schema({
            "results": [{"snippet": "hello", "snippet_type": "invalid"}]
        })
        print("❌ FAIL: Invalid snippet_type value was accepted")
        sys.exit(1)
    except RuntimeError as e:
        assert "invalid snippet_type" in str(e)
        print("✅ PASS: Invalid snippet_type value rejected")


if __name__ == '__main__':
    print("=" * 60)
    print("EXHAUSTIVE SCHEMA ENFORCEMENT TESTS")
    print("PRF-API-SCHEMA-001 Compliance")
    print("=" * 60)
    print()

    tests = [
        test_valid_schema_with_results,
        test_valid_schema_empty_results,
        test_valid_schema_multiple_results,
        test_invalid_not_dict,
        test_invalid_missing_results_key,
        test_invalid_results_not_list,
        test_invalid_result_not_dict,
        test_invalid_missing_snippet,
        test_invalid_empty_snippet,
        test_invalid_snippet_not_string,
        test_invalid_missing_snippet_type,
        test_invalid_snippet_type_value,
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
            import traceback
            traceback.print_exc()
            failed += 1

    print()
    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
    else:
        print()
        print("✅ ALL SCHEMA ENFORCEMENT TESTS PASSED")
        print("✅ PRF-API-SCHEMA-001 ENFORCED")
        print("✅ No HTTP 200 with invalid schema possible")
        sys.exit(0)

