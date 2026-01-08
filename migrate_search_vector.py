#!/usr/bin/env python3
"""
PRF-Compliant Migration: Add search_vector Column + Trigger
- Ensures chat_history.search_vector exists
- Populates it for existing rows from content->>'response_text'
- Adds BEFORE INSERT/UPDATE trigger for automatic population
- Runs end-to-end search verification
- Captures full evidence for PRF audit (Rules 0, 2, 9, 21, 22, 28, 29, 33)
"""

import sys
from conversation_manager import ConversationManager
import logging
import datetime

# ==========================
# Logging Setup (Evidence - Rule 29)
# ==========================
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = f'prf_migration_{timestamp}.log'

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

def capture_schema_state(cursor, label):
    """Rule 0: Capture BEFORE/AFTER states"""
    cursor.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name='chat_history'
        ORDER BY ordinal_position
    """)
    schema = cursor.fetchall()
    prf_log_step(f"{label}: chat_history schema", 
                 "\n".join([f"  {row[0]:20} {row[1]:15} nullable={row[2]:3} default={row[3]}" 
                           for row in schema]))
    return schema

def ensure_search_vector_column(cursor):
    """Rule 28: Add search_vector column if missing"""
    logger.info("Adding search_vector column if not exists...")
    cursor.execute("""
        ALTER TABLE chat_history
        ADD COLUMN IF NOT EXISTS search_vector tsvector;
    """)
    prf_log_step("Add search_vector column", "Executed ALTER TABLE ADD COLUMN IF NOT EXISTS")

def create_trigger_function(cursor):
    """Rule 28: Create trigger function to auto-populate search_vector"""
    logger.info("Creating trigger function...")
    cursor.execute("""
        CREATE OR REPLACE FUNCTION chat_history_search_vector_trigger()
        RETURNS trigger AS $$
        BEGIN
            -- Extract response_text from JSONB content and create tsvector
            NEW.search_vector := to_tsvector('english', 
                COALESCE(NEW.content->>'response_text', '')
            );
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)
    prf_log_step("Trigger function creation", 
                 "Function chat_history_search_vector_trigger() created/replaced")

def create_trigger(cursor):
    """Rule 28: Attach trigger to chat_history table"""
    logger.info("Creating trigger...")
    cursor.execute("""
        DROP TRIGGER IF EXISTS trg_chat_history_search_vector ON chat_history;
    """)
    cursor.execute("""
        CREATE TRIGGER trg_chat_history_search_vector
        BEFORE INSERT OR UPDATE ON chat_history
        FOR EACH ROW EXECUTE FUNCTION chat_history_search_vector_trigger();
    """)
    prf_log_step("Trigger creation", 
                 "Trigger trg_chat_history_search_vector created on chat_history")

def create_gin_index(cursor):
    """Rule 28: Create GIN index on search_vector"""
    logger.info("Creating GIN index...")
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS chat_history_search_vector_idx
        ON chat_history USING GIN(search_vector);
    """)
    prf_log_step("GIN index creation", 
                 "Index chat_history_search_vector_idx created")

def populate_existing_rows(cursor):
    """Rule 21: Populate search_vector for all existing rows"""
    logger.info("Populating search_vector for existing rows...")
    
    # Get count before
    cursor.execute("SELECT COUNT(*) FROM chat_history WHERE search_vector IS NULL")
    null_count_before = cursor.fetchone()[0]
    
    # Update all rows
    cursor.execute("""
        UPDATE chat_history
        SET search_vector = to_tsvector('english', 
            COALESCE(content->>'response_text', '')
        );
    """)
    
    # Get count after
    cursor.execute("SELECT COUNT(*) FROM chat_history")
    total_rows = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM chat_history WHERE search_vector IS NULL")
    null_count_after = cursor.fetchone()[0]
    
    prf_log_step("Populate existing rows", 
                 f"Total rows: {total_rows}\n"
                 f"NULL before: {null_count_before}\n"
                 f"NULL after: {null_count_after}\n"
                 f"Updated: {null_count_before - null_count_after}")

def end_to_end_search_test(cursor, test_query="button"):
    """Rule 9, 22: End-to-end search verification"""
    logger.info(f"Running end-to-end search test with query: '{test_query}'")
    
    cursor.execute("""
        SELECT 
            id,
            content->>'response_text' AS response_text,
            ts_rank(search_vector, plainto_tsquery('english', %s)) AS rank
        FROM chat_history
        WHERE search_vector @@ plainto_tsquery('english', %s)
        ORDER BY rank DESC
        LIMIT 5;
    """, (test_query, test_query))
    
    results = cursor.fetchall()
    
    evidence = f"Search query: '{test_query}'\nResults found: {len(results)}\n"
    if results:
        evidence += "\nTop 5 results:\n"
        for i, row in enumerate(results, 1):
            msg_id, response_text, rank = row
            preview = response_text[:100] if response_text else "(empty)"
            evidence += f"  {i}. ID={msg_id}, rank={rank:.4f}, text={preview}...\n"
    
    prf_log_step("End-to-End Search Test", evidence)
    
    return len(results) > 0

# ==========================
# Main Migration Workflow
# ==========================
def main():
    logger.info("="*60)
    logger.info("PRF-COMPLIANT MIGRATION: search_vector Column + Trigger")
    logger.info("="*60)
    logger.info(f"Log file: {log_file}\n")
    
    # Connect to database
    cm = ConversationManager()
    cursor = cm.pg_conn.cursor()
    
    try:
        # BEFORE state (Rule 0)
        before_schema = capture_schema_state(cursor, "BEFORE")
        
        # Migration steps
        ensure_search_vector_column(cursor)
        create_trigger_function(cursor)
        create_trigger(cursor)
        create_gin_index(cursor)
        populate_existing_rows(cursor)
        
        # Commit changes
        cm.pg_conn.commit()
        logger.info("\n✅ Migration committed successfully")
        
        # AFTER state (Rule 0)
        after_schema = capture_schema_state(cursor, "AFTER")
        
        # End-to-end test (Rule 9, 22)
        test_passed = end_to_end_search_test(cursor, "button")
        
        if test_passed:
            logger.info("\n✅ END-TO-END SEARCH TEST PASSED")
        else:
            logger.warning("\n⚠️ END-TO-END SEARCH TEST FAILED: No results found")
        
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

