-- Trail Phase 9: AI Brain - Conversation & Memory
-- Creates conversations table with vector embeddings (requires pgvector extension)

-- Enable pgvector extension (for vector similarity search)
CREATE EXTENSION IF NOT EXISTS vector;

-- Conversations table with semantic memory
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    role VARCHAR(20) NOT NULL,  -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    tool_calls JSONB,  -- stores tool name and arguments
    tool_call_id VARCHAR(100),  -- to match tool responses
    timestamp TIMESTAMP DEFAULT NOW(),
    embedding vector(384)  -- sentence-transformers all-MiniLM-L6-v2 produces 384-dim vectors
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_conversations_role ON conversations(role);

-- Vector index for semantic search (IVF Flat for efficiency)
CREATE INDEX IF NOT EXISTS idx_conversations_embedding ON conversations
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
