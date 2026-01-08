#!/bin/bash
# PRF Compliance Verification Script
# Run this before every commit to ensure all invariants are enforced

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║         PRF COMPLIANCE VERIFICATION                        ║"
echo "║         Production Readiness Framework                     ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Function to run a test and track results
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Testing: $test_name"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if eval "$test_command" > /tmp/test_output.log 2>&1; then
        echo -e "${GREEN}✅ PASS${NC}: $test_name"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "${RED}❌ FAIL${NC}: $test_name"
        echo "Error output:"
        cat /tmp/test_output.log | tail -20
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo ""
}

# Test 1: Database Boundary Normalization
run_test "PRF-DATA-SHAPE-001: Database Boundary Normalization" \
    "python3 test_exhaustive_types.py"

# Test 2: API Schema Enforcement
run_test "PRF-API-SCHEMA-001: API Schema Enforcement" \
    "python3 test_schema_enforcement.py"

# Test 3: End-to-End Enforcement
run_test "PRF-E2E: Complete Enforcement Chain" \
    "./test_e2e_enforcement.sh"

# Test 4: Code Quality Checks
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Code Quality: Verifying Enforcement Patterns"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check for normalize_message_content usage
if grep -q "normalize_message_content" conversation_manager.py; then
    echo -e "${GREEN}✅${NC} normalize_message_content() exists"
else
    echo -e "${RED}❌${NC} normalize_message_content() missing"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Check for enforce_search_response_schema usage
if grep -q "enforce_search_response_schema" api_server.py; then
    echo -e "${GREEN}✅${NC} enforce_search_response_schema() exists"
else
    echo -e "${RED}❌${NC} enforce_search_response_schema() missing"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Check for extract_snippet_or_fail usage
if grep -q "extract_snippet_or_fail" snippet_extraction.py; then
    echo -e "${GREEN}✅${NC} extract_snippet_or_fail() exists"
else
    echo -e "${RED}❌${NC} extract_snippet_or_fail() missing"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Check for veracity assertions
if grep -q "assert isinstance" conversation_manager.py; then
    echo -e "${GREEN}✅${NC} Veracity assertions present"
else
    echo -e "${YELLOW}⚠️${NC}  No veracity assertions found"
fi

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    TEST RESULTS                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Total Tests:  $TOTAL_TESTS"
echo -e "Passed:       ${GREEN}$PASSED_TESTS${NC}"
echo -e "Failed:       ${RED}$FAILED_TESTS${NC}"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                                                            ║"
    echo "║              ✅ PRF COMPLIANCE VERIFIED ✅                 ║"
    echo "║                                                            ║"
    echo "║  All invariants enforced. System is production-ready.     ║"
    echo "║                                                            ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Enforced Rules:"
    echo "  ✅ PRF-DATA-SHAPE-001: Database boundary normalization"
    echo "  ✅ PRF-NFC-001: No false completion (fail loud)"
    echo "  ✅ PRF-API-SCHEMA-001: Schema enforcement at API layer"
    echo "  ✅ Zero bypass paths"
    echo ""
    exit 0
else
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                                                            ║"
    echo "║              ❌ PRF COMPLIANCE FAILED ❌                   ║"
    echo "║                                                            ║"
    echo "║  Fix all failures before committing.                      ║"
    echo "║                                                            ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    exit 1
fi

