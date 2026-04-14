"""Verification test for Phase 9.5: Brain Hardening - Cost, Cache & Single Interface."""
import sys
sys.path.insert(0, '.')

passed = 0
failed = 0

def test(name, fn):
    global passed, failed
    try:
        fn()
        print(f"  PASS: {name}")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {name} => {e}")
        failed += 1

print("=== Phase 9.5 Verification Tests ===\n")

# Test 1: Budget functions exist
def t1():
    from src.ai.brain.budget import (
        get_current_month_spend,
        get_budget_limit,
        check_budget_alert,
        record_llm_usage,
    )
    assert callable(get_current_month_spend)
    assert callable(get_budget_limit)
    assert callable(check_budget_alert)
    assert callable(record_llm_usage)
test("Budget system: all functions present", t1)

# Test 2: Gamification engine exists
def t2():
    from src.ai.brain.gamification import GamificationEngine, get_gamification_engine
    engine = get_gamification_engine()
    assert hasattr(engine, 'award_daily_points')
    assert hasattr(engine, 'award_project_finisher_badge')
    assert hasattr(engine, 'get_user_stats')
test("Gamification engine: all methods present", t2)

# Test 3: Gamification points calculation
def t3():
    from unittest.mock import patch, MagicMock

    with patch('src.ai.brain.gamification.SessionLocal') as mock_db:
        mock_instance = MagicMock()
        mock_prefs = MagicMock()
        mock_prefs.total_points = 0
        mock_prefs.current_streak = 0
        mock_prefs.longest_streak = 0
        mock_instance.query.return_value.first.return_value = mock_prefs
        mock_db.return_value = mock_instance

        from src.ai.brain.gamification import GamificationEngine
        engine = GamificationEngine()

        # Test 100% adherence
        result = engine.award_daily_points(100, 3)
        assert result["points_awarded"] == 13  # 10 + 3*1

        # Test 80% adherence
        result = engine.award_daily_points(85, 1)
        assert result["points_awarded"] == 6  # 5 + 1

        # Test 50% adherence
        result = engine.award_daily_points(60, 0)
        assert result["points_awarded"] == 2

        # Test low adherence
        result = engine.award_daily_points(30, 0)
        assert result["points_awarded"] == 0
test("Gamification points: correct calculation for all tiers", t3)

# Test 4: ORM models exist
def t4():
    from src.models.database.models import UserAchievement, BudgetTracking
    assert hasattr(UserAchievement, 'achievement_type')
    assert hasattr(UserAchievement, 'achievement_name')
    assert hasattr(UserAchievement, 'value')
    assert hasattr(BudgetTracking, 'cost')
    assert hasattr(BudgetTracking, 'model')
    assert hasattr(BudgetTracking, 'tokens_used')
test("ORM: UserAchievement + BudgetTracking models with all fields", t4)

# Test 5: CLI brain has --channel flag
def t5():
    from src.cli.commands.brain import ask
    param_names = [p.name for p in ask.params]
    assert 'channel' in param_names
test("CLI: brain ask has --channel flag", t5)

# Test 6: Channel options are correct
def t6():
    from src.cli.commands.brain import ask
    channel_param = next(p for p in ask.params if p.name == 'channel')
    assert 'cli' in channel_param.type.choices
    assert 'slack' in channel_param.type.choices
    assert 'notion' in channel_param.type.choices
test("CLI: brain --channel accepts cli, slack, notion", t6)

# Test 7: Migration file exists
def t7():
    import os
    m19 = os.path.join('migrations', '019_create_user_achievements.sql')
    assert os.path.exists(m19), f'Migration missing: {m19}'
    with open(m19) as f:
        content = f.read()
    assert 'CREATE TABLE IF NOT EXISTS user_achievements' in content
    assert 'achievement_type' in content
    assert 'achievement_name' in content
    assert 'budget_tracking' in content.lower() or 'budget' in content.lower()
test("Migration: 019_create_user_achievements.sql correct", t7)

# Test 8: Streak badge thresholds defined
def t8():
    from src.ai.brain.gamification import STREAK_BADGES
    assert 7 in STREAK_BADGES
    assert 14 in STREAK_BADGES
    assert 30 in STREAK_BADGES
test("Streak badges: 7, 14, 30 day thresholds defined", t8)

# Test 9: Budget alert threshold is 80%
def t9():
    from src.ai.brain.budget import BUDGET_ALERT_THRESHOLD
    assert BUDGET_ALERT_THRESHOLD == 0.80
test("Budget alert: 80% threshold configured", t9)

# Test 10: .env.example has SLACK_WEBHOOK_URL
def t10():
    import os
    env_example = os.path.join('.env.example')
    assert os.path.exists(env_example)
    with open(env_example) as f:
        content = f.read()
    assert 'SLACK_WEBHOOK_URL' in content
test(".env.example: SLACK_WEBHOOK_URL documented", t10)

# Summary
print(f"\n{'='*40}")
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL PHASE 9.5 TESTS PASSED")
else:
    print("SOME TESTS FAILED")
    sys.exit(1)
