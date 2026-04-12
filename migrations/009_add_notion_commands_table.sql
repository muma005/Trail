-- Trail Phase 5: Notion AI Agent
-- Creates notion_commands table for storing @ai commands

CREATE TABLE IF NOT EXISTS notion_commands (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    page_id VARCHAR(100) NOT NULL,
    block_id VARCHAR(100) NOT NULL,
    command TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, processing, completed, failed
    response_block_id VARCHAR(100),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP,
    UNIQUE (page_id, block_id)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_notion_commands_status ON notion_commands(status);
CREATE INDEX IF NOT EXISTS idx_notion_commands_project ON notion_commands(project_id);
CREATE INDEX IF NOT EXISTS idx_notion_commands_page ON notion_commands(page_id);
