-- Trail Phase 7.5: Untracked Work Detection & Prompts
-- Creates untracked_sessions table and time_logs table

-- Untracked sessions: detected work periods without commits
CREATE TABLE IF NOT EXISTS untracked_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    duration_minutes INT NOT NULL,
    resolved BOOLEAN DEFAULT FALSE,
    assigned_task_id UUID REFERENCES notion_tasks(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Time logs: manual or auto-detected work sessions
CREATE TABLE IF NOT EXISTS time_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    task_id UUID REFERENCES notion_tasks(id) ON DELETE SET NULL,
    user_id UUID DEFAULT gen_random_uuid(),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    duration_minutes INT NOT NULL,
    task_type VARCHAR(50) DEFAULT 'manual',  -- manual, untracked, prompted
    source VARCHAR(50) DEFAULT 'manual',     -- manual, prompted, auto-detected
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_untracked_project ON untracked_sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_untracked_resolved ON untracked_sessions(resolved);
CREATE INDEX IF NOT EXISTS idx_time_logs_project ON time_logs(project_id);
CREATE INDEX IF NOT EXISTS idx_time_logs_source ON time_logs(source);
CREATE INDEX IF NOT EXISTS idx_time_logs_start ON time_logs(start_time);
