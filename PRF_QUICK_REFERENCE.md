# PRF Quick Reference Card

## 🚀 Quick Start

```bash
# Run all PRF compliance tests
./verify_prf_compliance.sh

# Run individual test suites
python3 test_exhaustive_types.py        # Database boundary tests
python3 test_schema_enforcement.py      # API schema tests
./test_e2e_enforcement.sh               # End-to-end tests
```

---

## 📋 The Three PRF Rules

### 1️⃣ PRF-DATA-SHAPE-001: Database Boundary Normalization
**Rule:** All downstream logic receives a guaranteed non-empty string.

**Where:** `conversation_manager.py::normalize_message_content()`

**Usage:**
```python
# ✅ CORRECT: Normalize at the boundary
full_content = self.normalize_message_content(result.get('full_content'))
# Now full_content is guaranteed to be a non-empty string

# ❌ WRONG: Don't assume data shape
full_content = result.get('full_content')  # Could be dict, None, empty!
```

---

### 2️⃣ PRF-NFC-001: No False Completion
**Rule:** Operations either succeed completely or fail loudly.

**Where:** `snippet_extraction.py::extract_snippet_or_fail()`

**Usage:**
```python
# ✅ CORRECT: Use extract_snippet_or_fail
try:
    snippet_data = extract_snippet_or_fail(full_content, query, snippet_type, context_lines)
    # snippet_data is guaranteed valid
except SnippetExtractionError as e:
    logger.error(f"Snippet extraction failed: {e}")
    raise  # Re-raise, don't swallow

# ❌ WRONG: Don't catch and return empty/default
try:
    snippet_data = extract_snippet_or_fail(...)
except:
    snippet_data = {"snippet": "", "snippet_type": "unknown"}  # NO!
```

---

### 3️⃣ PRF-API-SCHEMA-001: API Schema Enforcement
**Rule:** HTTP 200 only if schema is valid. No exceptions.

**Where:** `api_server.py::enforce_search_response_schema()`

**Usage:**
```python
# ✅ CORRECT: Enforce schema before returning HTTP 200
try:
    payload = {"success": True, "results": results}
    payload = enforce_search_response_schema(payload)
    return jsonify(payload), 200
except Exception as e:
    logger.critical("Schema violation", exc_info=e)
    return jsonify({"success": False, "error": str(e)}), 500

# ❌ WRONG: Return HTTP 200 with error message
return jsonify({"error": "Something went wrong"}), 200  # NO!
```

---

## 🔍 Common Patterns

### Pattern 1: Reading from Database
```python
# ✅ CORRECT
cursor.execute("SELECT content FROM chat_history WHERE id=%s", (msg_id,))
result = cursor.fetchone()
full_content = self.normalize_message_content(result['content'])
# Now full_content is guaranteed non-empty string

# ❌ WRONG
full_content = result['content']  # Could be dict, None, empty!
if isinstance(full_content, dict):
    full_content = full_content.get('text', '')  # Reactive patching!
```

### Pattern 2: Extracting Snippets
```python
# ✅ CORRECT
normalized_text = self.normalize_message_content(raw_content)
snippet_data = extract_snippet_or_fail(normalized_text, query, snippet_type, context_lines)

# ❌ WRONG
snippet_data = extract_snippet_or_fail(raw_content, ...)  # Bypasses normalization!
```

### Pattern 3: API Responses
```python
# ✅ CORRECT
try:
    results = process_search(query)
    payload = {"success": True, "results": results}
    payload = enforce_search_response_schema(payload)
    return jsonify(payload), 200
except Exception as e:
    return jsonify({"success": False, "error": str(e)}), 500

# ❌ WRONG
results = process_search(query)
return jsonify({"results": results}), 200  # No schema validation!
```

---

## ⚠️ Common Mistakes

### Mistake 1: Silent Fallbacks
```python
# ❌ WRONG
try:
    text = normalize_message_content(raw)
except:
    text = ""  # Silent fallback - hides data issues!

# ✅ CORRECT
text = normalize_message_content(raw)  # Let it raise if invalid
```

### Mistake 2: Assuming Data Shapes
```python
# ❌ WRONG
content = result['content']
if content:  # Assumes string, but could be dict!
    snippet = content[:100]

# ✅ CORRECT
content = self.normalize_message_content(result['content'])
snippet = content[:100]  # Now guaranteed to be string
```

### Mistake 3: Returning HTTP 200 with Errors
```python
# ❌ WRONG
if error:
    return jsonify({"error": "Failed"}), 200

# ✅ CORRECT
if error:
    return jsonify({"success": False, "error": "Failed"}), 500
```

---

## 🧪 Testing Checklist

Before committing code:

- [ ] Run `./verify_prf_compliance.sh`
- [ ] All 28+ tests pass
- [ ] No new silent fallbacks added
- [ ] All data boundaries have normalization
- [ ] All API responses have schema enforcement
- [ ] Error messages include context (message_id, type, etc.)

---

## 📊 Test Coverage

| Component | Test File | Tests | Coverage |
|-----------|-----------|-------|----------|
| Normalization | `test_exhaustive_types.py` | 16 | All types |
| Schema | `test_schema_enforcement.py` | 12 | All fields |
| E2E | `test_e2e_enforcement.sh` | 4 groups | Full chain |

---

## 🆘 Troubleshooting

### "Message content is None"
**Cause:** Database returned NULL  
**Fix:** Investigate why content is NULL, fix data issue

### "Unsupported content type: list"
**Cause:** Database schema changed or data corrupted  
**Fix:** Check database schema, ensure content is JSONB or TEXT

### "Snippet missing or empty"
**Cause:** Normalization or extraction failed  
**Fix:** Check logs for upstream error, ensure normalization happened

### "Invalid snippet_type: unknown"
**Cause:** Classification logic returned invalid value  
**Fix:** Check `classify_snippet_type()` function

---

## 📚 Documentation

- **Full Details:** `PRF_ENFORCEMENT.md`
- **Implementation:** `IMPLEMENTATION_SUMMARY.md`
- **Verification:** `FINAL_VERIFICATION_REPORT.md`
- **This Card:** `PRF_QUICK_REFERENCE.md`

---

## 🎯 Remember

1. **Fail Loud, Not Silent** - Errors should raise exceptions
2. **Enforce at Boundaries** - Normalize at DB, validate at API
3. **No Assumptions** - Always validate data shapes
4. **Test Everything** - 100% pass rate required
5. **Document Context** - Logs should include IDs and types

---

**Status:** ✅ PRF-Compliant  
**Last Verified:** 2026-01-07  
**Test Pass Rate:** 100% (28+ tests)

