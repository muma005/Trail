-- Trail Phase 9.5: Brain Hardening - Gamification & Budget Tracking
-- Creates user_achievements table and budget tracking columns

-- User achievements: stores points, streaks, and badges
CREATE TABLE IF NOT EXISTS user_achievements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID DEFAULT gen_random_uuid(),
    achievement_type VARCHAR(50) NOT NULL,  -- 'streak', 'badge', 'points'
    achievement_name VARCHAR(100) NOT NULL,  -- e.g., '7_day_streak', 'plan_adherence_master'
    value INT DEFAULT 0,
    earned_at TIMESTAMP DEFAULT NOW(),
    metadata TEXT  -- JSON metadata
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_user_achievements_user_type ON user_achievements(user_id, achievement_type);
CREATE INDEX IF NOT EXISTS idx_user_achievements_name ON user_achievements(achievement_name);
CREATE INDEX IF NOT EXISTS idx_user_achievements_earned ON user_achievements(earned_at DESC);

-- Add gamification columns to user_preferences (if not present)
ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS total_points INT DEFAULT 0;
ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS current_streak INT DEFAULT 0;
ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS longest_streak INT DEFAULT 0;
ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS llm_budget_monthly_usd DECIMAL(10,2) DEFAULT 10.00;
ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS last_budget_alert_sent TIMESTAMP;

-- Budget tracking table (if not present from earlier phases)
CREATE TABLE IF NOT EXISTS budget_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID DEFAULT gen_random_uuid(),
    cost DECIMAL(10,4) NOT NULL,
    model VARCHAR(100),
    tokens_used INT,
    timestamp TIMESTAMP DEFAULT NOW(),
    description TEXT
);

CREATE INDEX IF NOT EXISTS idx_budget_tracking_user_ts ON budget_tracking(user_id, timestamp DESC);
