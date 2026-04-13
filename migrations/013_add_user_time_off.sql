-- Trail Phase 6.5: Calendar, Holidays, Switch Costs
-- Creates user_time_off and switch_costs tables

-- User time-off (holidays, PTO)
CREATE TABLE IF NOT EXISTS user_time_off (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID DEFAULT gen_random_uuid(),  -- fixed UUID for single-user
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    reason VARCHAR(100),
    is_working BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Switch costs between projects
CREATE TABLE IF NOT EXISTS switch_costs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    to_project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    penalty_minutes INT DEFAULT 10,
    sample_count INT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (from_project_id, to_project_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_user_time_off_dates ON user_time_off(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_switch_costs_from ON switch_costs(from_project_id);
CREATE INDEX IF NOT EXISTS idx_switch_costs_to ON switch_costs(to_project_id);
