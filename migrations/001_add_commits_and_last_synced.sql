-- Trail Phase 1: Migration for GitHub Sync
-- Adds commits table and last_synced_at column to projects

-- Add last_synced_at to projects table (nullable, incremental sync)
ALTER TABLE projects ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMP;

-- Create commits table
CREATE TABLE IF NOT EXISTS commits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    commit_sha VARCHAR(40) UNIQUE NOT NULL,
    author_name VARCHAR(255),
    author_email VARCHAR(255),
    commit_date TIMESTAMP NOT NULL,
    message TEXT NOT NULL,
    files_changed JSONB,
    lines_added INTEGER DEFAULT 0,
    lines_deleted INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_commits_project_id ON commits(project_id);
CREATE INDEX IF NOT EXISTS idx_commits_commit_date ON commits(commit_date);
CREATE INDEX IF NOT EXISTS idx_projects_last_synced ON projects(last_synced_at);
