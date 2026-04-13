-- Trail Phase 7: Verification & Auto-Reassignment
-- Creates planned_task_verification table

CREATE TABLE IF NOT EXISTS planned_task_verification (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    daily_plan_id UUID REFERENCES daily_plans(id) ON DELETE SET NULL,
    task_id UUID REFERENCES notion_tasks(id) ON DELETE SET NULL,
    expected_commit_sha VARCHAR(40),
    expected_status_change VARCHAR(50),
    actual_commit_sha VARCHAR(40),
    actual_status VARCHAR(50),
    verified_at TIMESTAMP DEFAULT NOW(),
    was_completed BOOLEAN DEFAULT FALSE,
    partial_progress_percentage DECIMAL(5,2),
    remaining_estimate_minutes INT,
    detection_method VARCHAR(50),  -- 'commits', 'status', 'subtasks', 'llm'
    missed_reason TEXT,
    reassigned_to_plan_id UUID REFERENCES daily_plans(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_ptv_daily_plan ON planned_task_verification(daily_plan_id);
CREATE INDEX IF NOT EXISTS idx_ptv_task ON planned_task_verification(task_id);
CREATE INDEX IF NOT EXISTS idx_ptv_verified_at ON planned_task_verification(verified_at);
CREATE INDEX IF NOT EXISTS idx_ptv_was_completed ON planned_task_verification(was_completed);
