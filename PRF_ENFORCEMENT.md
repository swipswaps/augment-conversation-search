# PRF Enforcement Documentation

## Overview

This document describes the **Production Readiness Framework (PRF)** enforcement mechanisms implemented in the Augment Conversation Manager. All rules are **executable, not just documented**. Violations cause immediate failures with detailed error messages.

---

## Core Principles

### 1. **Fail Loud, Not Silent**
- All errors raise exceptions with context
- No silent fallbacks or defaults
- No "waiting for user input" messages in HTTP 200 responses
- Logs include full context (message_id, conversation_id, data types)

### 2. **Enforce at Boundaries**
- Database → Application: `normalize_message_content()`
- Application → API: `enforce_search_response_schema()`
- No assumptions about data shapes anywhere else

### 3. **Veracity Checks**
- Every critical operation includes assertions
- Pre-conditions and post-conditions validated
- Type safety enforced at runtime

---

## PRF-DATA-SHAPE-001: Database Boundary Normalization

### Rule
**All downstream logic receives a guaranteed non-empty string.**

### Implementation
Location: `conversation_manager.py::normalize_message_content()`

```python
def normalize_message_content(self, raw) -> str:
    """
    HARD INVARIANTS:
    - Input: str, dict, or reject
    - Output: non-empty string
    - No silent fallbacks
    """
```

### Veracity Checks
1. ✅ Input is not None
2. ✅ Input type is str or dict
3. ✅ If dict, extract from known keys: `response_text`, `content`, `text`
4. ✅ Result is non-empty after stripping whitespace
5. ✅ Post-condition: output is non-empty string

### Rejected Inputs
- `None` → RuntimeError
- Empty string `""` → RuntimeError
- Whitespace-only `"   "` → RuntimeError
- Empty dict `{}` → RuntimeError
- Dict without text keys → RuntimeError
- Invalid types (int, float, list, bool, bytes) → RuntimeError

### Test Coverage
File: `test_exhaustive_types.py`
- 16 test cases covering all valid and invalid types
- 100% pass rate required

---

## PRF-NFC-001: No False Completion

### Rule
**Operations either succeed completely or fail loudly. No partial success.**

### Implementation
Location: `snippet_extraction.py::extract_snippet_or_fail()`

```python
def extract_snippet_or_fail(full_content: str, query: str, ...) -> dict:
    """
    HARD INVARIANTS:
    - Input is normalized string (enforced at boundary)
    - Returns dict with snippet and snippet_type
    - Raises SnippetExtractionError if query not found
    """
```

### Veracity Checks
1. ✅ Input is string (type check)
2. ✅ Query is non-empty
3. ✅ Snippet extraction succeeds or raises exception
4. ✅ Result contains required keys: `snippet`, `snippet_type`

### Failure Modes
- Query not found → SnippetExtractionError
- Invalid input type → RuntimeError
- Empty content → RuntimeError (caught at normalization)

### Test Coverage
File: `test_e2e_enforcement.sh` (Test 3)
- Valid extraction
- Reject dict, empty string, None

---

## PRF-API-SCHEMA-001: API Schema Enforcement

### Rule
**HTTP 200 responses MUST conform to the search schema. No exceptions.**

### Implementation
Location: `api_server.py::enforce_search_response_schema()`

```python
def enforce_search_response_schema(payload: dict) -> dict:
    """
    HARD INVARIANTS:
    - Payload is dict
    - Contains 'results' key with list value
    - Each result has non-empty 'snippet' (string)
    - Each result has valid 'snippet_type' (code|prose)
    """
```

### Veracity Checks
1. ✅ Payload is dict
2. ✅ 'results' key exists
3. ✅ 'results' is a list
4. ✅ Each result is a dict
5. ✅ Each result has non-empty string 'snippet'
6. ✅ Each result has valid 'snippet_type' (code or prose)

### Rejected Schemas
- Non-dict payload → RuntimeError
- Missing 'results' key → RuntimeError
- 'results' not a list → RuntimeError
- Result item not a dict → RuntimeError
- Missing 'snippet' field → RuntimeError
- Empty snippet → RuntimeError
- Non-string snippet → RuntimeError
- Missing 'snippet_type' → RuntimeError
- Invalid snippet_type value → RuntimeError

### Test Coverage
File: `test_schema_enforcement.py`
- 12 test cases covering all valid and invalid schemas
- 100% pass rate required

---

## Enforcement Chain

### Search Flow
```
1. Database Query
   ↓
2. normalize_message_content()  ← PRF-DATA-SHAPE-001
   ↓ (guaranteed non-empty string)
3. extract_snippet_or_fail()    ← PRF-NFC-001
   ↓ (dict with snippet + type)
4. enforce_search_response_schema() ← PRF-API-SCHEMA-001
   ↓ (validated payload)
5. HTTP 200 with valid JSON
```

### Ordering Verification
File: `test_e2e_enforcement.sh` (Test 4)
- Verifies normalization happens before extraction
- No bypass possible

---

## Running Tests

### Individual Test Suites
```bash
# Database boundary normalization
python3 test_exhaustive_types.py

# API schema enforcement
python3 test_schema_enforcement.py

# End-to-end validation
./test_e2e_enforcement.sh
```

### Expected Output
All tests must pass with 0 failures:
```
✅ ALL EXHAUSTIVE TYPE TESTS PASSED
✅ PRF-DATA-SHAPE-001 ENFORCED

✅ ALL SCHEMA ENFORCEMENT TESTS PASSED
✅ PRF-API-SCHEMA-001 ENFORCED

✅ ALL END-TO-END ENFORCEMENT TESTS PASSED
```

---

## Error Handling

### Production Behavior
- All PRF violations → HTTP 500
- Detailed error logged with context
- No silent degradation
- No fallback messages

### Example Error Log
```python
logger.error(
    "DATA NORMALIZATION FAILURE: Message content is None",
    extra={
        "message_id": "12345",
        "conversation_id": "conv-abc",
        "raw_type": "NoneType",
        "error": "Message content is None"
    }
)
```

---

## Maintenance

### Adding New Features
1. Identify all data boundaries
2. Add veracity checks at each boundary
3. Write exhaustive tests for all edge cases
4. Update this document with new invariants

### Modifying Existing Code
1. Never remove veracity checks
2. Never add silent fallbacks
3. Always fail loud with context
4. Update tests to cover new edge cases

---

## Summary

| Rule | Location | Test File | Status |
|------|----------|-----------|--------|
| PRF-DATA-SHAPE-001 | `conversation_manager.py` | `test_exhaustive_types.py` | ✅ Enforced |
| PRF-NFC-001 | `snippet_extraction.py` | `test_e2e_enforcement.sh` | ✅ Enforced |
| PRF-API-SCHEMA-001 | `api_server.py` | `test_schema_enforcement.py` | ✅ Enforced |

**System Status: PRF-Compliant and Production-Ready**

