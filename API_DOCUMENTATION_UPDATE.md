# API Documentation Update - ChatGPT UX Fixes

## Overview

This document describes the **new UX metadata fields** added to search results as part of the ChatGPT UX fixes implementation.

---

## Search Endpoint

### `GET /api/search/messages`

Search for messages across all conversations with full-text search.

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | string | Yes | Search query (supports fuzzy matching) |
| `limit` | integer | No | Max results (default: 20) |
| `type` | string | No | Filter by snippet type: "code" or "prose" |
| `date_from` | string | No | ISO date (YYYY-MM-DD) |
| `date_to` | string | No | ISO date (YYYY-MM-DD) |

#### Response Schema

```json
{
  "success": true,
  "result_count": 3,
  "query_interpretation": {
    "original_query": "are correct",
    "processed_query": "correct",
    "stop_words_filtered": ["are"]
  },
  "results": [
    {
      "message_id": "uuid",
      "conversation_id": "uuid",
      "conversation_name": "string",
      "role": "user" | "assistant",
      "timestamp": "ISO-8601",
      "snippet_type": "code" | "prose",
      "snippet": "string (with <mark> tags)",
      
      // Structured context (Sourcegraph-style)
      "context_before": ["line1", "line2"],
      "matched_lines": ["matched line"],
      "context_after": ["line1", "line2"],
      
      // Match metadata
      "match_count": 1,
      "match_positions": [42],
      "match_line": 5,
      "start_line": 2,
      "end_line": 8,
      
      // ✨ NEW: UX metadata (ChatGPT fixes)
      "match_type": "exact" | "fuzzy" | "fallback",
      "snippet_confidence": "high" | "medium" | "low",
      "snippet_note": "string or null"
    }
  ]
}
```

---

## New UX Metadata Fields

### `match_type`

**Type**: `string`  
**Values**: `"exact"` | `"fuzzy"` | `"fallback"`  
**Required**: Yes

Indicates how the query matched the content:

- **`"exact"`**: Query appears verbatim in content (case-insensitive)
  - Example: Query "button" found in "Click the button"
  
- **`"fuzzy"`**: Query matched via word boundaries, stemming, or stop word filtering
  - Example: Query "are correct" matched "Correction: The correct port..."
  - Stop words ("are") filtered, "correct" matched as word prefix
  
- **`"fallback"`**: No direct match found, showing context excerpt
  - Example: PostgreSQL found match via stemming, but snippet extraction couldn't locate it
  - Returns first N lines as context

**Frontend Usage**:
```javascript
if (result.match_type === 'fuzzy') {
  // Show fuzzy match indicator (~)
} else if (result.match_type === 'fallback') {
  // Show low confidence indicator (?)
}
```

---

### `snippet_confidence`

**Type**: `string`  
**Values**: `"high"` | `"medium"` | `"low"`  
**Required**: Yes

Indicates confidence level of the match:

- **`"high"`**: Exact match, high confidence
  - User can trust this result
  - No special UI treatment needed
  
- **`"medium"`**: Fuzzy match, medium confidence
  - Result is likely relevant but not exact
  - Show warning badge (~)
  
- **`"low"`**: Fallback match, low confidence
  - Result may not be relevant
  - Show caution badge (?)
  - Display explanation in snippet_note

**Frontend Usage**:
```javascript
const badge = {
  high: '',           // No badge
  medium: '~',        // Yellow badge
  low: '?'            // Red badge
}[result.snippet_confidence];
```

---

### `snippet_note`

**Type**: `string | null`  
**Required**: Yes (can be null)

Human-readable explanation of the match quality:

- **`null`**: Exact match, no explanation needed
  
- **String**: Explanation for fuzzy or fallback matches
  - Example: `"Fuzzy match (stemmed/partial): found 'correct' variants"`
  - Example: `"No direct match found for 'xyz' - showing context excerpt"`

**Frontend Usage**:
```javascript
if (result.snippet_note) {
  // Show info icon with tooltip
  <span title={result.snippet_note}>ℹ️</span>
}
```

---

## Match Type Examples

### Example 1: Exact Match

**Query**: `"button"`  
**Content**: `"Click the button to submit"`

**Response**:
```json
{
  "snippet": "Click the <mark>button</mark> to submit",
  "match_type": "exact",
  "snippet_confidence": "high",
  "snippet_note": null
}
```

---

### Example 2: Fuzzy Match (Stop Words)

**Query**: `"are correct"`  
**Content**: `"Correction: The correct port is 5432"`

**Response**:
```json
{
  "snippet": "Correction: The <mark>correct</mark> port is 5432",
  "match_type": "fuzzy",
  "snippet_confidence": "medium",
  "snippet_note": "Fuzzy match (stemmed/partial): found 'correct' variants"
}
```

**Explanation**: 
- "are" filtered as stop word
- "correct" matched as word prefix

---

### Example 3: Fuzzy Match (Stemming)

**Query**: `"settings"`  
**Content**: `"Change the setting in config.json"`

**Response**:
```json
{
  "snippet": "Change the <mark>setting</mark> in config.json",
  "match_type": "fuzzy",
  "snippet_confidence": "medium",
  "snippet_note": "Fuzzy match (stemmed/partial): found 'setting' variants"
}
```

**Explanation**: 
- "settings" → "setting" (stemming)

---

### Example 4: Fallback Match

**Query**: `"xyzabc"`  
**Content**: `"This is some content that PostgreSQL matched via complex stemming"`

**Response**:
```json
{
  "snippet": "This is some content that PostgreSQL...",
  "match_type": "fallback",
  "snippet_confidence": "low",
  "snippet_note": "No direct match found for 'xyzabc' - showing context excerpt"
}
```

**Explanation**: 
- PostgreSQL found match via stemming
- Snippet extraction couldn't locate exact match
- Returns first 5 lines as context

---

## Error Handling

### HTTP 200 OK (Always for Search)

All search queries return HTTP 200, even if:
- No results found
- Query is ambiguous
- Fuzzy matching applied
- Fallback used

**Example (No Results)**:
```json
{
  "success": true,
  "result_count": 0,
  "results": []
}
```

### HTTP 400 Bad Request

Only for invalid input:
- Empty query
- Invalid date format
- Invalid type parameter

**Example**:
```json
{
  "success": false,
  "error": "Query parameter 'q' is required"
}
```

### HTTP 500 Internal Server Error

**Only for system failures**:
- Database connection failure
- System crash

**Never for**:
- Search ambiguity
- Fuzzy matches
- Missing results

---

## Frontend Integration Guide

### Display Confidence Badges

```javascript
function renderResult(result) {
  const badges = {
    high: '',
    medium: '<span class="badge medium" title="Fuzzy match">~</span>',
    low: '<span class="badge low" title="Low confidence">?</span>'
  };
  
  const badge = badges[result.snippet_confidence];
  const note = result.snippet_note 
    ? `<div class="note">ℹ️ ${result.snippet_note}</div>`
    : '';
  
  return `
    <div class="result">
      <div class="header">
        ${result.role} ${badge}
      </div>
      ${note}
      <div class="snippet">${result.snippet}</div>
    </div>
  `;
}
```

### CSS Styling

```css
.badge.medium {
  background: #fff3cd;
  color: #856404;
  border: 1px solid #ffc107;
}

.badge.low {
  background: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

.note {
  background: #f0f7ff;
  border-left: 3px solid #0366d6;
  padding: 0.5rem;
  margin: 0.5rem 0;
}
```

---

## Migration Guide

### For Existing Clients

**Backward Compatibility**: ✅ Fully compatible

Existing clients will continue to work because:
1. All existing fields remain unchanged
2. New fields are additive (not breaking)
3. HTTP status codes unchanged (200 for success)

**Recommended Updates**:
1. Add UI for confidence badges
2. Display snippet notes as tooltips
3. Update error handling (expect 200, not 500)

---

## Summary

The new UX metadata fields provide:
- ✅ **Transparency**: Users see match quality
- ✅ **Reliability**: No HTTP 500 for ambiguity
- ✅ **Better UX**: Explanations for fuzzy matches

This is the production-ready approach for search UX.

