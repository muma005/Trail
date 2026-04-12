-- Trail Phase 4.1: Abandonment Thresholds
-- Adds warning_days, critical_days, archive_days to user_preferences
-- Also adds status column to projects and notification tracking

-- Add abandonment thresholds to user_preferences
ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS warning_days INT DEFAULT 7;
ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS critical_days INT DEFAULT 14;
ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS archive_days INT DEFAULT 21;

-- Add status column to projects (active, archived, paused)
ALTER TABLE projects ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active';

-- Add last_commit_date for quick idle calculation
ALTER TABLE projects ADD COLUMN IF NOT EXISTS last_commit_date TIMESTAMP;

-- Add notification tracking columns to prevent duplicate alerts
ALTER TABLE projects ADD COLUMN IF NOT EXISTS last_warning_notified_at TIMESTAMP;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS last_critical_notified_at TIMESTAMP;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_last_commit_date ON projects(last_commit_date);
