"""
Snippet extraction with UX-first best-effort approach.

CRITICAL ARCHITECTURAL CHANGE (per ChatGPT critique):
- Snippet extraction NEVER throws exceptions for match ambiguity
- Fuzzy/stemmed matches are EXPECTED behavior, not errors
- Returns match metadata so frontend can make UX decisions
- HTTP 500 is FORBIDDEN for search ambiguity

This implements ChatGPT's FIX 1-6.
"""

import re
from typing import Dict, List, Optional


# PostgreSQL English stop words (commonly ignored in full-text search)
STOP_WORDS = {
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'but', 'by', 'for', 'if',
    'in', 'into', 'is', 'it', 'no', 'not', 'of', 'on', 'or', 'such',
    'that', 'the', 'their', 'then', 'there', 'these', 'they', 'this',
    'to', 'was', 'will', 'with'
}


class SnippetExtractionError(RuntimeError):
    """
    ONLY raised for data integrity violations (empty content, invalid types).
    NEVER raised for match ambiguity - that's a UX state, not an error.
    """
    pass


def extract_snippet_or_fail(
    *,
    full_content: str,
    query: str,
    snippet_type: str,
    context_lines: int = 3,
) -> dict:
    """
    Extract a snippet with context around the match.

    BEST-EFFORT EXTRACTION (UX-first approach):
    - If exact match found: return high-confidence snippet
    - If fuzzy match found: return medium-confidence snippet with explanation
    - If no match found: return low-confidence context excerpt

    NEVER raises exceptions for match ambiguity - that's a UX state, not an error.
    Only raises for data integrity violations (empty content, invalid types).

    NOTE: Content normalization happens at the database boundary.
    This function assumes it receives a validated non-empty string.
    """
    # INVARIANT 1: Content must be non-empty string
    # (Type enforcement - should never fail if boundary is correct)
    if not isinstance(full_content, str):
        raise SnippetExtractionError(
            f"BOUNDARY VIOLATION: full_content must be string, got {type(full_content)}. "
            f"This indicates normalize_message_content() was bypassed."
        )

    if not full_content or not full_content.strip():
        raise SnippetExtractionError(
            "BOUNDARY VIOLATION: full_content is empty. "
            "This indicates normalize_message_content() was bypassed."
        )

    lines = full_content.splitlines()
    
    # Handle empty lines array
    if not lines:
        raise SnippetExtractionError("full_content has no lines")

    # INVARIANT 2: Query must match somewhere
    # PostgreSQL full-text search uses stemming, so we need fuzzy matching
    query_lower = query.lower()
    import re

    # PostgreSQL English stop words (commonly ignored in full-text search)
    # These words are often filtered out during indexing
    STOP_WORDS = {
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'but', 'by', 'for', 'if',
        'in', 'into', 'is', 'it', 'no', 'not', 'of', 'on', 'or', 'such',
        'that', 'the', 'their', 'then', 'there', 'these', 'they', 'this',
        'to', 'was', 'will', 'with'
    }

    # Strategy 1: Exact substring match (case-insensitive)
    match_indices = [
        i for i, line in enumerate(lines)
        if query_lower in line.lower()
    ]

    # Strategy 2: If no exact match, try word boundary match for stemmed variants
    # E.g., "button" should match "buttons", "buttoned", etc.
    if not match_indices and len(query_lower) > 3:
        # For single-word queries, match as word prefix
        if ' ' not in query_lower:
            pattern = re.compile(r'\b' + re.escape(query_lower), re.IGNORECASE)
            match_indices = [
                i for i, line in enumerate(lines)
                if pattern.search(line)
            ]
        else:
            # For multi-word queries, match each word as a prefix
            # E.g., "are correct" should match lines containing "correction"
            # (ignoring stop words like "are")
            query_words = query_lower.split()

            # Filter out stop words from query
            significant_words = [w for w in query_words if w not in STOP_WORDS]

            # If all words are stop words, fall back to exact match
            if not significant_words:
                significant_words = query_words

            for i, line in enumerate(lines):
                line_lower = line.lower()
                # Check if all significant query words (or their stems) appear in the line
                all_words_match = True
                for word in significant_words:
                    # Try exact match first
                    if word in line_lower:
                        continue
                    # Try word prefix match (stemming)
                    word_pattern = re.compile(r'\b' + re.escape(word), re.IGNORECASE)
                    if word_pattern.search(line):
                        continue
                    # Word not found
                    all_words_match = False
                    break

                if all_words_match:
                    match_indices.append(i)

    # BEST-EFFORT FALLBACK: If no match found, return context excerpt
    # This handles cases where PostgreSQL matched via stemming/fuzzy logic
    # but we can't find the exact query in the content
    if not match_indices:
        # Return first few lines as context (low-confidence match)
        idx = 0
        start = 0
        end = min(len(lines), context_lines * 2)
        match_type = "fuzzy"
        snippet_confidence = "low"
        snippet_note = f"Snippet does not contain literal query '{query}' - matched via stemming/fuzzy search"
    else:
        # Use first match (high-confidence)
        idx = match_indices[0]
        start = max(0, idx - context_lines)
        end = min(len(lines), idx + context_lines + 1)
        match_type = "exact" if query.lower() in lines[idx].lower() else "stem"
        snippet_confidence = "high" if match_type == "exact" else "medium"
        snippet_note = None

    # Extract structured context (Sourcegraph-style)
    context_before = lines[start:idx]
    matched_lines = [lines[idx]] if idx < len(lines) else [lines[0] if lines else ""]
    context_after = lines[idx + 1:end]

    # Build combined snippet for backward compatibility
    snippet_lines = context_before + matched_lines + context_after
    snippet_text = '\n'.join(snippet_lines)

    # BEST-EFFORT: If snippet is empty, use first 200 chars of content
    if not snippet_text.strip():
        snippet_text = full_content[:200] + "..." if len(full_content) > 200 else full_content
        matched_lines = [snippet_text]
        snippet_confidence = "low"
        snippet_note = "Unable to extract structured snippet - showing content preview"

    # Count total matches in content (for metadata)
    total_matches = len(match_indices)

    # Calculate character positions for each match in the matched line
    # This provides Sourcegraph-style match position metadata
    import re
    matched_line_text = matched_lines[0]
    match_positions = []

    # Find all occurrences of query in the matched line
    # Use case-insensitive search
    pattern = re.compile(re.escape(query_lower), re.IGNORECASE)
    for match in pattern.finditer(matched_line_text.lower()):
        match_positions.append({
            'start': match.start(),
            'end': match.end(),
            'length': match.end() - match.start()
        })

    # If no exact matches, try prefix matching (for stemmed variants)
    if not match_positions and len(query_lower) > 3:
        prefix_pattern = re.compile(r'\b' + re.escape(query_lower), re.IGNORECASE)
        for match in prefix_pattern.finditer(matched_line_text):
            # Find the end of the word
            word_end = match.start()
            while word_end < len(matched_line_text) and matched_line_text[word_end].isalnum():
                word_end += 1
            match_positions.append({
                'start': match.start(),
                'end': word_end,
                'length': word_end - match.start()
            })

    return {
        "snippet_type": snippet_type,
        "snippet": snippet_text,  # Backward compatibility
        "context_before": context_before,  # Sourcegraph-style structured context
        "matched_lines": matched_lines,
        "context_after": context_after,
        "match_line": idx,
        "start_line": start,
        "end_line": end,
        "total_lines": len(lines),
        "match_count": total_matches,  # How many matches in this message
        "match_positions": match_positions,  # Character offsets within matched line
        # UX metadata for match confidence and explanation
        "match_type": match_type,
        "snippet_confidence": snippet_confidence,
        "snippet_note": snippet_note,
    }


def classify_snippet_type(content: str) -> str:
    """
    Classify content as code or prose.

    Code indicators:
    - Indentation (4+ spaces or tabs)
    - Code keywords
    - Code punctuation patterns

    NOTE: Assumes content is already normalized at DB boundary.
    """
    # Type check - should never fail if boundary is correct
    if not isinstance(content, str):
        # Defensive fallback, but this indicates a boundary violation
        return 'prose'

    code_indicators = [
        '```',
        'def ',
        'class ',
        'import ',
        'function ',
        'const ',
        'let ',
        'var ',
        'print(',
        'console.',
        '    ',  # 4 spaces
        '\t',    # tab
    ]

    return 'code' if any(ind in content for ind in code_indicators) else 'prose'


def extract_snippet_best_effort(
    content: str,
    query: str,
    context_lines: int = 2
) -> Dict:
    """
    UX-FIRST BEST-EFFORT SNIPPET EXTRACTION (ChatGPT FIX 1-4).

    This function NEVER throws exceptions for match ambiguity.
    It returns a dict with match metadata so the frontend can make UX decisions.

    Three-tier extraction strategy:
    1. Exact match (case-insensitive substring)
    2. Stemmed/fuzzy match (word boundaries, ignoring stop words)
    3. Fallback (first N lines as context excerpt)

    Returns:
        Dict with keys:
            - snippet: str (extracted text)
            - context_before: List[str]
            - matched_lines: List[str]
            - context_after: List[str]
            - match_count: int
            - match_positions: List[int]
            - match_line: int (first match line number)
            - start_line: int
            - end_line: int
            - match_type: str ("exact" | "fuzzy" | "fallback")
            - snippet_confidence: str ("high" | "medium" | "low")
            - snippet_note: str (explanation for user)

    NEVER raises exceptions except for data integrity violations.
    """
    # Data integrity check (only case where exception is allowed)
    if not isinstance(content, str) or not content.strip():
        raise SnippetExtractionError(
            "BOUNDARY VIOLATION: content must be non-empty string"
        )

    lines = content.splitlines()
    if not lines:
        lines = [content]  # Fallback for single-line content

    query_lower = query.lower()

    # STRATEGY 1: Exact substring match (case-insensitive)
    match_indices = [
        i for i, line in enumerate(lines)
        if query_lower in line.lower()
    ]

    if match_indices:
        return _build_snippet_result(
            lines=lines,
            match_indices=match_indices,
            context_lines=context_lines,
            match_type="exact",
            snippet_confidence="high",
            snippet_note=None
        )

    # STRATEGY 2: Fuzzy match (word boundaries, stemming, stop word filtering)
    query_words = [w for w in query_lower.split() if w not in STOP_WORDS]

    if query_words:
        fuzzy_match_indices = []
        for i, line in enumerate(lines):
            line_lower = line.lower()
            # Check if any significant query word appears as word prefix
            for word in query_words:
                pattern = re.compile(r'\b' + re.escape(word), re.IGNORECASE)
                if pattern.search(line_lower):
                    fuzzy_match_indices.append(i)
                    break

        if fuzzy_match_indices:
            return _build_snippet_result(
                lines=lines,
                match_indices=fuzzy_match_indices,
                context_lines=context_lines,
                match_type="fuzzy",
                snippet_confidence="medium",
                snippet_note=f"Fuzzy match (stemmed/partial): found '{query_words[0]}' variants"
            )

    # STRATEGY 3: Fallback (no match found - return context excerpt)
    # This is NOT an error - it's expected behavior for fuzzy search
    fallback_lines = min(5, len(lines))
    return {
        "snippet": "\n".join(lines[:fallback_lines]),
        "context_before": [],
        "matched_lines": lines[:fallback_lines],
        "context_after": [],
        "match_count": 0,
        "match_positions": [],
        "match_line": 0,
        "start_line": 0,
        "end_line": fallback_lines - 1,
        "match_type": "fallback",
        "snippet_confidence": "low",
        "snippet_note": f"No direct match found for '{query}' - showing context excerpt"
    }


def _build_snippet_result(
    lines: List[str],
    match_indices: List[int],
    context_lines: int,
    match_type: str,
    snippet_confidence: str,
    snippet_note: Optional[str]
) -> Dict:
    """Helper to build snippet result dict."""
    first_match = match_indices[0]
    start = max(0, first_match - context_lines)
    end = min(len(lines), first_match + context_lines + 1)

    context_before = lines[start:first_match]
    matched_lines = [lines[i] for i in match_indices if start <= i < end]
    context_after = lines[first_match + 1:end]

    return {
        "snippet": "\n".join(lines[start:end]),
        "context_before": context_before,
        "matched_lines": matched_lines,
        "context_after": context_after,
        "match_count": len(match_indices),
        "match_positions": match_indices,
        "match_line": first_match,
        "start_line": start,
        "end_line": end - 1,
        "match_type": match_type,
        "snippet_confidence": snippet_confidence,
        "snippet_note": snippet_note
    }
