-- ============================================================================
-- FUZZY SEARCH MIGRATION: PostgreSQL Trigram Extension
-- ============================================================================
-- Purpose: Enable fuzzy matching for typos, partial words, and autocomplete
-- Author: Modern Search UX Implementation
-- Date: 2026-01-08
-- ============================================================================

-- STEP 1: Install pg_trgm extension (trigram matching)
-- This enables similarity() function and % operator
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- STEP 2: Create GIN index on content (cast to text) for fast fuzzy search
-- This makes similarity queries ~100x faster
-- Note: content is JSONB, so we cast to text for trigram indexing
CREATE INDEX IF NOT EXISTS idx_chat_history_content_trgm
ON chat_history USING gin ((content::text) gin_trgm_ops);

-- STEP 3: Create GIN index on search_vector for word statistics
-- This enables ts_stat() for "did you mean" functionality
CREATE INDEX IF NOT EXISTS idx_chat_history_search_vector_gin
ON chat_history USING gin (search_vector);

-- STEP 4: Set similarity threshold (0.3 = 70% similar, adjust as needed)
-- Lower = more lenient (catches more typos)
-- Higher = stricter (fewer false positives)
SET pg_trgm.similarity_threshold = 0.3;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Test 1: Verify extension is installed
SELECT extname, extversion
FROM pg_extension
WHERE extname = 'pg_trgm';
-- Expected: pg_trgm | 1.6 (or similar)

-- Test 2: Verify indexes exist
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'chat_history'
    AND (indexname LIKE '%trgm%' OR indexname LIKE '%search_vector%');
-- Expected: idx_chat_history_content_trgm and idx_chat_history_search_vector_gin

-- Test 3: Test fuzzy matching (example with typo)
-- This should return words similar to 'absolutel' (typo of 'absolutely')
SELECT word, similarity(word, 'absolutel') as sim
FROM ts_stat('SELECT search_vector FROM chat_history')
WHERE similarity(word, 'absolutel') > 0.6
ORDER BY sim DESC
LIMIT 5;
-- Expected output (if 'absolutely' exists in your data):
-- word         | sim
-- -------------+--------
-- absolutely   | 0.889
-- absolute     | 0.833

-- Test 4: Test content-level fuzzy search
SELECT content, similarity(content::text, 'absolutel') as sim
FROM chat_history
WHERE content::text % 'absolutel'
ORDER BY sim DESC
LIMIT 5;
-- Expected: Rows containing 'absolutely', 'absolute', etc.

-- ============================================================================
-- CONFIGURATION NOTES
-- ============================================================================

-- Similarity threshold tuning:
-- - 0.1-0.2: Very fuzzy (catches distant typos, more false positives)
-- - 0.3-0.4: Balanced (good for 1-2 character typos)
-- - 0.5-0.6: Strict (only close matches)
-- - 0.7+: Very strict (almost exact match)

-- To change threshold globally:
-- ALTER DATABASE augment_conversations SET pg_trgm.similarity_threshold = 0.3;

-- To change threshold per session:
-- SET pg_trgm.similarity_threshold = 0.3;

-- ============================================================================
-- ROLLBACK (if needed)
-- ============================================================================

-- To remove fuzzy search:
-- DROP INDEX IF EXISTS idx_chat_history_content_trgm;
-- DROP INDEX IF EXISTS idx_chat_history_search_vector_trgm;
-- DROP EXTENSION IF EXISTS pg_trgm;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

-- Verify migration success
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') THEN
        RAISE NOTICE '✅ Fuzzy search migration complete!';
        RAISE NOTICE '   - pg_trgm extension installed';
        RAISE NOTICE '   - Trigram indexes created';
        RAISE NOTICE '   - Ready for fuzzy matching';
    ELSE
        RAISE EXCEPTION '❌ Migration failed: pg_trgm extension not found';
    END IF;
END $$;

