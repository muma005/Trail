-- Trail Phase 8: Learning & Personalization
-- Creates learned_patterns table for storing duration multipliers, focus peaks, etc.

CREATE TABLE IF NOT EXISTS learned_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID DEFAULT gen_random_uuid(),
    pattern_type VARCHAR(50) NOT NULL,  -- duration_multiplier, focus_peak_hour, empty_promise_multiplier
    context JSONB,  -- e.g., {"task_type": "unit_test", "size_tag": "medium"}
    value DECIMAL(10,4) NOT NULL,
    confidence DECIMAL(5,4) DEFAULT 0,
    sample_count INT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_learned_patterns_user_type ON learned_patterns(user_id, pattern_type);
CREATE INDEX IF NOT EXISTS idx_learned_patterns_context ON learned_patterns USING GIN(context);
CREATE INDEX IF NOT EXISTS idx_learned_patterns_type_context ON learned_patterns(pattern_type, context);
