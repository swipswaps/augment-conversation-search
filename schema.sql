-- Augment Conversation Data Management Schema
-- PostgreSQL schema for storing conversation exports with deduplication

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- For text search

-- Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id VARCHAR(255) UNIQUE NOT NULL, -- Original Augment conversation ID
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    last_interacted_at TIMESTAMPTZ NOT NULL,
    exported_at TIMESTAMPTZ NOT NULL,
    total_messages INTEGER DEFAULT 0,
    total_tool_states INTEGER DEFAULT 0,
    file_size_mb DECIMAL(10, 2),
    content_hash VARCHAR(64) UNIQUE NOT NULL, -- SHA256 hash for deduplication
    metadata JSONB,
    created_in_db TIMESTAMPTZ DEFAULT NOW(),
    updated_in_db TIMESTAMPTZ DEFAULT NOW()
);

-- Chat history table
CREATE TABLE IF NOT EXISTS chat_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    message_index INTEGER NOT NULL,
    role VARCHAR(50) NOT NULL, -- 'user' or 'assistant'
    content JSONB NOT NULL,
    content_hash VARCHAR(64) NOT NULL, -- SHA256 hash for deduplication
    timestamp TIMESTAMPTZ,
    created_in_db TIMESTAMPTZ DEFAULT NOW(),
    search_vector TSVECTOR, -- Full-text search vector (auto-populated by trigger)
    UNIQUE(conversation_id, message_index),
    UNIQUE(content_hash) -- Prevent duplicate messages across conversations
);

-- Tool use states table
CREATE TABLE IF NOT EXISTS tool_use_states (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    tool_use_id VARCHAR(255) NOT NULL,
    request_id VARCHAR(255),
    phase INTEGER,
    result JSONB,
    content_hash VARCHAR(64) UNIQUE NOT NULL, -- SHA256 hash for deduplication
    created_in_db TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(conversation_id, tool_use_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_conversations_conversation_id ON conversations(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at);
CREATE INDEX IF NOT EXISTS idx_conversations_content_hash ON conversations(content_hash);

CREATE INDEX IF NOT EXISTS idx_chat_history_conversation_id ON chat_history(conversation_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_message_index ON chat_history(message_index);
CREATE INDEX IF NOT EXISTS idx_chat_history_content_hash ON chat_history(content_hash);
CREATE INDEX IF NOT EXISTS idx_chat_history_role ON chat_history(role);
CREATE INDEX IF NOT EXISTS idx_chat_history_timestamp ON chat_history(timestamp);

CREATE INDEX IF NOT EXISTS idx_tool_use_states_conversation_id ON tool_use_states(conversation_id);
CREATE INDEX IF NOT EXISTS idx_tool_use_states_tool_use_id ON tool_use_states(tool_use_id);
CREATE INDEX IF NOT EXISTS idx_tool_use_states_content_hash ON tool_use_states(content_hash);

-- GIN indexes for JSONB search
CREATE INDEX IF NOT EXISTS idx_conversations_metadata_gin ON conversations USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_chat_history_content_gin ON chat_history USING GIN (content);
CREATE INDEX IF NOT EXISTS idx_tool_use_states_result_gin ON tool_use_states USING GIN (result);

-- Full-text search index on conversation names
CREATE INDEX IF NOT EXISTS idx_conversations_name_trgm ON conversations USING GIN (name gin_trgm_ops);

-- Full-text search index on message content using PostgreSQL's built-in full-text search
-- This is MUCH faster than ILIKE for text search
-- NOTE: We use search_vector column (auto-populated by trigger) instead of inline to_tsvector
CREATE INDEX IF NOT EXISTS idx_chat_history_search_vector ON chat_history USING GIN (search_vector);

-- Function to update updated_in_db timestamp
CREATE OR REPLACE FUNCTION update_updated_in_db_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_in_db = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_in_db
CREATE TRIGGER update_conversations_updated_in_db
    BEFORE UPDATE ON conversations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_in_db_column();

-- Function to auto-populate search_vector from content->>'response_text'
-- Includes normalization: lowercase, whitespace collapse, trim
CREATE OR REPLACE FUNCTION chat_history_search_vector_trigger()
RETURNS TRIGGER AS $$
DECLARE
    normalized_text text;
BEGIN
    -- Normalize: remove extra whitespace, lowercase
    -- Note: to_tsvector already handles lowercasing and some normalization,
    -- but we add explicit whitespace normalization for consistency
    normalized_text := regexp_replace(
        lower(COALESCE(NEW.content->>'response_text', '')),
        '\s+',
        ' ',
        'g'
    );

    -- Trim leading/trailing whitespace
    normalized_text := trim(normalized_text);

    NEW.search_vector := to_tsvector('english', normalized_text);
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

-- Trigger to auto-populate search_vector on INSERT/UPDATE
CREATE TRIGGER trg_chat_history_search_vector
    BEFORE INSERT OR UPDATE ON chat_history
    FOR EACH ROW
    EXECUTE FUNCTION chat_history_search_vector_trigger();

-- View for conversation statistics
CREATE OR REPLACE VIEW conversation_stats AS
SELECT 
    c.id,
    c.conversation_id,
    c.name,
    c.created_at,
    c.last_interacted_at,
    c.total_messages,
    c.total_tool_states,
    c.file_size_mb,
    COUNT(DISTINCT ch.id) AS actual_message_count,
    COUNT(DISTINCT tus.id) AS actual_tool_state_count,
    c.created_in_db,
    c.updated_in_db
FROM conversations c
LEFT JOIN chat_history ch ON c.id = ch.conversation_id
LEFT JOIN tool_use_states tus ON c.id = tus.conversation_id
GROUP BY c.id;

-- View for duplicate detection
CREATE OR REPLACE VIEW duplicate_messages AS
SELECT 
    content_hash,
    COUNT(*) as duplicate_count,
    ARRAY_AGG(id) as message_ids,
    ARRAY_AGG(conversation_id) as conversation_ids
FROM chat_history
GROUP BY content_hash
HAVING COUNT(*) > 1;

-- View for duplicate tool states
CREATE OR REPLACE VIEW duplicate_tool_states AS
SELECT 
    content_hash,
    COUNT(*) as duplicate_count,
    ARRAY_AGG(id) as tool_state_ids,
    ARRAY_AGG(conversation_id) as conversation_ids
FROM tool_use_states
GROUP BY content_hash
HAVING COUNT(*) > 1;

-- Comments for documentation
COMMENT ON TABLE conversations IS 'Stores Augment conversation metadata with deduplication via content_hash';
COMMENT ON TABLE chat_history IS 'Stores individual messages from conversations with deduplication';
COMMENT ON TABLE tool_use_states IS 'Stores tool execution states with deduplication';
COMMENT ON COLUMN conversations.content_hash IS 'SHA256 hash of entire conversation for deduplication';
COMMENT ON COLUMN chat_history.content_hash IS 'SHA256 hash of message content for deduplication';
COMMENT ON COLUMN tool_use_states.content_hash IS 'SHA256 hash of tool state for deduplication';

