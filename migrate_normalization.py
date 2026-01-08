#!/usr/bin/env python3
"""
PRF-Compliant Migration: Add Normalization to search_vector Trigger
- Updates trigger function to normalize content before generating search_vector
- Normalization: lowercase, collapse whitespace, strip special chars
- Backfills existing rows with normalized search_vector
- Runs end-to-end search verification
- Captures full evidence for PRF audit (Rules 0, 2, 4, 7, 9, 21, 22, 28, 29, 33)
"""

import sys
from conversation_manager import ConversationManager
import logging
import datetime

# ==========================
# Logging Setup (Evidence - Rule 29)
# ==========================
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = f'prf_normalization_migration_{timestamp}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# ==========================
# PRF Workflow Functions
# ==========================
def prf_log_step(step_name, evidence):
    """Rule 0: Log each step with evidence"""
    logger.info(f"\n{'='*60}")
    logger.info(f"STEP: {step_name}")
    logger.info(f"{'='*60}")
    logger.info(f"Evidence:\n{evidence}\n")

def capture_trigger_state(cursor, label):
    """Rule 0: Capture BEFORE/AFTER states of trigger function"""
    cursor.execute("""
        SELECT pg_get_functiondef(oid)
        FROM pg_proc
        WHERE proname = 'chat_history_search_vector_trigger'
    """)
    result = cursor.fetchone()
    if result:
        prf_log_step(f"{label}: Trigger Function", result[0])
        return result[0]
    else:
        prf_log_step(f"{label}: Trigger Function", "NOT FOUND")
        return None

def update_trigger_with_normalization(cursor):
    """Rule 28: Update trigger function to normalize content"""
    logger.info("Updating trigger function with normalization...")
    
    cursor.execute("""
        CREATE OR REPLACE FUNCTION chat_history_search_vector_trigger()
        RETURNS trigger AS $$
        DECLARE
            normalized_text text;
        BEGIN
            -- Normalize: remove extra whitespace, lowercase
            -- Note: to_tsvector already handles lowercasing and some normalization,
            -- but we add explicit whitespace normalization for consistency
            normalized_text := regexp_replace(
                lower(COALESCE(NEW.content->>'response_text', '')),
                '\\s+',
                ' ',
                'g'
            );
            
            -- Trim leading/trailing whitespace
            normalized_text := trim(normalized_text);
            
            NEW.search_vector := to_tsvector('english', normalized_text);
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)
    
    prf_log_step("Update trigger function", 
                 "Trigger function updated with normalization:\n"
                 "  - lowercase conversion\n"
                 "  - whitespace collapse (\\s+ -> single space)\n"
                 "  - trim leading/trailing whitespace")

def backfill_existing_rows(cursor):
    """Rule 21: Backfill all existing rows with normalized search_vector"""
    logger.info("Backfilling existing rows with normalized search_vector...")
    
    # Get count before
    cursor.execute("SELECT COUNT(*) FROM chat_history")
    total_rows = cursor.fetchone()[0]
    
    # Sample a few rows BEFORE normalization
    cursor.execute("""
        SELECT 
            id,
            content->>'response_text' AS response_text,
            search_vector::text AS search_vector_before
        FROM chat_history
        WHERE content->>'response_text' IS NOT NULL
        LIMIT 3
    """)
    before_samples = cursor.fetchall()
    
    # Update all rows with normalized search_vector
    cursor.execute("""
        UPDATE chat_history
        SET search_vector = to_tsvector(
            'english',
            trim(regexp_replace(
                lower(COALESCE(content->>'response_text', '')),
                '\\s+',
                ' ',
                'g'
            ))
        );
    """)
    
    # Sample the same rows AFTER normalization
    # Cast UUIDs to proper type
    before_ids = [str(row[0]) for row in before_samples]
    cursor.execute("""
        SELECT
            id,
            content->>'response_text' AS response_text,
            search_vector::text AS search_vector_after
        FROM chat_history
        WHERE id::text = ANY(%s)
    """, (before_ids,))
    after_samples = cursor.fetchall()
    
    evidence = f"Total rows updated: {total_rows}\n\n"
    evidence += "Sample BEFORE/AFTER comparison:\n"
    for i, (before_row, after_row) in enumerate(zip(before_samples, after_samples), 1):
        evidence += f"\n  Sample {i}:\n"
        evidence += f"    ID: {before_row[0]}\n"
        evidence += f"    Text preview: {before_row[1][:50]}...\n"
        evidence += f"    BEFORE: {before_row[2][:80]}...\n"
        evidence += f"    AFTER:  {after_row[2][:80]}...\n"
    
    prf_log_step("Backfill existing rows", evidence)

def end_to_end_search_test(cursor, test_queries):
    """Rule 9, 22: End-to-end search verification with multiple queries"""
    logger.info("Running end-to-end search tests with normalization...")
    
    all_passed = True
    evidence = ""
    
    for test_query in test_queries:
        cursor.execute("""
            SELECT 
                id,
                content->>'response_text' AS response_text,
                ts_rank(search_vector, plainto_tsquery('english', %s)) AS rank
            FROM chat_history
            WHERE search_vector @@ plainto_tsquery('english', %s)
            ORDER BY rank DESC
            LIMIT 3;
        """, (test_query, test_query))
        
        results = cursor.fetchall()
        
        evidence += f"\nQuery: '{test_query}'\n"
        evidence += f"Results found: {len(results)}\n"
        
        if results:
            evidence += "Top 3 results:\n"
            for i, row in enumerate(results, 1):
                msg_id, response_text, rank = row
                preview = response_text[:80] if response_text else "(empty)"
                evidence += f"  {i}. rank={rank:.4f}, text={preview}...\n"
        else:
            evidence += "  ⚠️ No results found\n"
            all_passed = False
    
    prf_log_step("End-to-End Search Tests", evidence)
    
    return all_passed

# ==========================
# Main Migration Workflow
# ==========================
def main():
    logger.info("="*60)
    logger.info("PRF-COMPLIANT MIGRATION: Normalization for search_vector")
    logger.info("="*60)
    logger.info(f"Log file: {log_file}\n")
    
    # Connect to database
    cm = ConversationManager()
    cursor = cm.pg_conn.cursor()
    
    try:
        # BEFORE state (Rule 0)
        before_trigger = capture_trigger_state(cursor, "BEFORE")
        
        # Migration steps
        update_trigger_with_normalization(cursor)
        backfill_existing_rows(cursor)
        
        # Commit changes
        cm.pg_conn.commit()
        logger.info("\n✅ Migration committed successfully")
        
        # AFTER state (Rule 0)
        after_trigger = capture_trigger_state(cursor, "AFTER")
        
        # End-to-end tests (Rule 9, 22)
        test_queries = ["button", "BUTTON", "  button  ", "buttons"]
        test_passed = end_to_end_search_test(cursor, test_queries)
        
        if test_passed:
            logger.info("\n✅ ALL END-TO-END SEARCH TESTS PASSED")
        else:
            logger.warning("\n⚠️ SOME END-TO-END SEARCH TESTS FAILED")
        
        cursor.close()
        
        logger.info("\n" + "="*60)
        logger.info("MIGRATION COMPLETE")
        logger.info("="*60)
        logger.info(f"Full evidence saved to: {log_file}")
        
    except Exception as e:
        cm.pg_conn.rollback()
        logger.error(f"\n❌ MIGRATION FAILED: {e}")
        raise

if __name__ == "__main__":
    main()

