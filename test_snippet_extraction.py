"""
Tests for snippet extraction.
These tests MUST fail if the system tries to return empty or invalid snippets.
"""

import pytest
from snippet_extraction import extract_snippet_or_fail, SnippetExtractionError, classify_snippet_type


def test_valid_code_snippet_extraction():
    """Test that valid code content produces a snippet with structure preserved."""
    content = """\
def hello():
    print("hello world")
    return True
"""
    result = extract_snippet_or_fail(
        full_content=content,
        query="print",
        snippet_type="code",
    )

    # MUST contain the match
    assert "print(" in result["snippet"]
    
    # MUST preserve newlines
    assert "\n" in result["snippet"]
    assert result["snippet"].count("\n") >= 1
    
    # MUST have metadata
    assert result["match_line"] >= 0
    assert result["snippet_type"] == "code"


def test_context_lines_included():
    """Test that context before and after the match is included."""
    content = """\
line 1
line 2
MATCH HERE
line 4
line 5
"""
    result = extract_snippet_or_fail(
        full_content=content,
        query="MATCH",
        snippet_type="prose",
        context_lines=2,
    )
    
    lines = result["snippet"].split("\n")
    
    # Should have: 2 before + 1 match + 2 after = 5 lines
    assert len(lines) == 5
    assert "MATCH HERE" in result["snippet"]
    assert "line 2" in result["snippet"]
    assert "line 4" in result["snippet"]


def test_empty_content_raises():
    """CRITICAL: Empty content MUST raise, never return empty snippet."""
    with pytest.raises(SnippetExtractionError, match="empty or missing"):
        extract_snippet_or_fail(
            full_content="",
            query="print",
            snippet_type="code",
        )


def test_whitespace_only_content_raises():
    """CRITICAL: Whitespace-only content MUST raise."""
    with pytest.raises(SnippetExtractionError):
        extract_snippet_or_fail(
            full_content="   \n\n   \n",
            query="print",
            snippet_type="code",
        )


def test_match_missing_raises():
    """CRITICAL: If query doesn't match, MUST raise (database integrity violation)."""
    with pytest.raises(SnippetExtractionError, match="not found in content"):
        extract_snippet_or_fail(
            full_content="hello world",
            query="print",
            snippet_type="prose",
        )


def test_case_insensitive_matching():
    """Test that matching is case-insensitive."""
    content = "PRINT something"
    result = extract_snippet_or_fail(
        full_content=content,
        query="print",
        snippet_type="code",
    )
    assert "PRINT" in result["snippet"]


def test_classify_code_vs_prose():
    """Test content type classification."""
    
    # Code examples
    assert classify_snippet_type("def foo():\n    pass") == "code"
    assert classify_snippet_type("import sys") == "code"
    assert classify_snippet_type("    indented code") == "code"
    assert classify_snippet_type("console.log('hi')") == "code"
    
    # Prose examples
    assert classify_snippet_type("This is plain text") == "prose"
    assert classify_snippet_type("A sentence without code.") == "prose"


def test_multiline_code_preserves_structure():
    """Test that multiline code blocks preserve indentation and newlines."""
    content = """\
def calculate():
    x = 10
    y = 20
    return x + y
"""
    result = extract_snippet_or_fail(
        full_content=content,
        query="return",
        snippet_type="code",
    )
    
    # MUST preserve indentation
    assert "    return x + y" in result["snippet"]
    
    # MUST preserve newlines
    assert result["snippet"].count("\n") >= 2


def test_snippet_never_empty_string():
    """CRITICAL: Snippet field must never be empty string."""
    content = "some content here"
    result = extract_snippet_or_fail(
        full_content=content,
        query="content",
        snippet_type="prose",
    )
    
    assert result["snippet"]
    assert result["snippet"].strip()
    assert len(result["snippet"]) > 0


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])

