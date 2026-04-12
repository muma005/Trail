-- Trail Phase 3: Progress Calculator & Report Generator
-- Creates project_snapshots table for daily progress tracking

CREATE TABLE IF NOT EXISTS project_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    snapshot_date DATE NOT NULL,
    total_tasks INT DEFAULT 0,
    completed_tasks INT DEFAULT 0,
    in_progress_tasks INT DEFAULT 0,
    blocked_tasks INT DEFAULT 0,
    not_started_tasks INT DEFAULT 0,
    total_commits INT DEFAULT 0,
    lines_of_code_added INT DEFAULT 0,
    completion_percentage_simple DECIMAL(5,2),
    completion_percentage_weighted DECIMAL(5,2),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (project_id, snapshot_date)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_project_snapshots_project_date ON project_snapshots(project_id, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_project_snapshots_date ON project_snapshots(snapshot_date);
