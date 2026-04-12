-- Trail Phase 1.5: Migration for scope filtering and commit parsing
-- Creates project_scopes table and adds parsed_task_id, needs_classification to commits

-- Project scopes: defines which branches/paths a project tracks
CREATE TABLE IF NOT EXISTS project_scopes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    scope_type VARCHAR(20) NOT NULL CHECK (scope_type IN ('branch', 'path')),
    scope_value TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (project_id, scope_type, scope_value)
);

-- Add commit parsing columns to commits table
ALTER TABLE commits ADD COLUMN IF NOT EXISTS parsed_task_id VARCHAR(100);
ALTER TABLE commits ADD COLUMN IF NOT EXISTS needs_classification BOOLEAN DEFAULT FALSE;

-- Indexes for faster orphan queries and scope lookups
CREATE INDEX IF NOT EXISTS idx_project_scopes_project_id ON project_scopes(project_id);
CREATE INDEX IF NOT EXISTS idx_commits_needs_classification ON commits(needs_classification) WHERE needs_classification = TRUE;
CREATE INDEX IF NOT EXISTS idx_commits_parsed_task_id ON commits(parsed_task_id);
