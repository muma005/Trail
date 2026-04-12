-- Trail Phase 0: Database Schema
-- Core identity: one project = one GitHub repo + one Notion database

-- Projects table: enforces the identity rule with UNIQUE constraints
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_key VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    github_repo_url TEXT NOT NULL UNIQUE,
    notion_database_id VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- User preferences: work hours and timezone (single user for now)
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_start TIME DEFAULT '09:00',
    work_end TIME DEFAULT '17:00',
    timezone VARCHAR(50) DEFAULT 'UTC',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Sync logs: audit trail for project creation and future syncs
CREATE TABLE IF NOT EXISTS sync_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    sync_type VARCHAR(20) NOT NULL,  -- 'project_creation', 'github', 'notion'
    status VARCHAR(20) NOT NULL,      -- 'success', 'failed', 'partial'
    message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_sync_logs_project_id ON sync_logs(project_id);
CREATE INDEX IF NOT EXISTS idx_sync_logs_created_at ON sync_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_projects_project_key ON projects(project_key);
