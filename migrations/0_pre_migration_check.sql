-- ============================================================================
-- PRE-MIGRATION CHECKS
-- ============================================================================
-- Run this BEFORE running 1_database_fuzzy_setup.sql
-- ============================================================================

-- Check 1: Is pg_trgm already installed?
SELECT 
    CASE 
        WHEN EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm')
        THEN '✅ pg_trgm already installed'
        ELSE '⚠️  pg_trgm NOT installed (will be installed by migration)'
    END as extension_status;

-- Check 2: How many rows in chat_history?
-- This helps estimate index creation time
SELECT 
    COUNT(*) as total_rows,
    CASE 
        WHEN COUNT(*) < 10000 THEN '✅ Small table (<10k rows) - indexing will be fast (<1 min)'
        WHEN COUNT(*) < 100000 THEN '⚠️  Medium table (10k-100k rows) - indexing may take 1-5 min'
        WHEN COUNT(*) < 1000000 THEN '⚠️  Large table (100k-1M rows) - indexing may take 5-10 min'
        ELSE '🔴 Very large table (>1M rows) - indexing may take 10+ min'
    END as indexing_estimate
FROM chat_history;

-- Check 3: Do the indexes already exist?
SELECT 
    indexname,
    CASE 
        WHEN indexname = 'idx_chat_history_content_trgm' THEN '⚠️  Will be skipped (already exists)'
        WHEN indexname = 'idx_chat_history_search_vector_gin' THEN '⚠️  Will be skipped (already exists)'
        ELSE '✅ New index'
    END as status
FROM pg_indexes
WHERE tablename = 'chat_history'
    AND (indexname LIKE '%trgm%' OR indexname LIKE '%search_vector%');

-- Check 4: Database size (to ensure enough disk space)
SELECT 
    pg_size_pretty(pg_database_size(current_database())) as database_size,
    CASE 
        WHEN pg_database_size(current_database()) < 1073741824 THEN '✅ Small DB (<1GB) - plenty of space'
        WHEN pg_database_size(current_database()) < 10737418240 THEN '⚠️  Medium DB (1-10GB) - ensure 20% free space'
        ELSE '🔴 Large DB (>10GB) - ensure 20% free space for indexing'
    END as space_recommendation;

-- ============================================================================
-- BACKUP RECOMMENDATION
-- ============================================================================

-- Before running the migration, create a backup:
-- pg_dump -U marketplace_user augment_conversations > backup_$(date +%Y%m%d_%H%M%S).sql

-- ============================================================================
-- READY TO PROCEED?
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'PRE-MIGRATION CHECK COMPLETE';
    RAISE NOTICE '============================================================';
    RAISE NOTICE '';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '1. Review the checks above';
    RAISE NOTICE '2. Create a backup (recommended):';
    RAISE NOTICE '   pg_dump -U marketplace_user augment_conversations > backup.sql';
    RAISE NOTICE '3. Run the migration:';
    RAISE NOTICE '   psql -U marketplace_user -d augment_conversations -f migrations/1_database_fuzzy_setup.sql';
    RAISE NOTICE '';
    RAISE NOTICE '============================================================';
END $$;

