-- Trail Phase 6: Smart Work Planner Core
-- Extends user_preferences, creates project_constraints table

-- Add planner preferences to user_preferences
ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS max_parallel_projects INT DEFAULT 2;
ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS constant_project_id UUID REFERENCES projects(id);
ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS deep_work_minutes INT DEFAULT 120;
ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS lunch_start TIME;
ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS lunch_end TIME;

-- Project constraints table for planning-specific data
CREATE TABLE IF NOT EXISTS project_constraints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID UNIQUE NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    estimated_remaining_hours DECIMAL(10,2) NOT NULL DEFAULT 0,
    deadline DATE,
    priority VARCHAR(20) DEFAULT 'Medium',  -- Critical, High, Medium, Low
    is_constant BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Daily plans table (for storing generated plans)
CREATE TABLE IF NOT EXISTS daily_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    plan_date DATE NOT NULL,
    allocated_minutes INT NOT NULL,
    tasks_planned JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (project_id, plan_date)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_project_constraints_project_id ON project_constraints(project_id);
CREATE INDEX IF NOT EXISTS idx_project_constraints_deadline ON project_constraints(deadline);
CREATE INDEX IF NOT EXISTS idx_daily_plans_date ON daily_plans(plan_date);
