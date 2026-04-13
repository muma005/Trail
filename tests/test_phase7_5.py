"""Verification test for Phase 7.5: Untracked Work & Prompts."""
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

print("=== Phase 7.5 Verification Tests ===\n")

# Test 1: Activity monitor exists
def t1():
    from src.services.verification.activity_monitor import (
        get_last_activity_timestamp,
        detect_untracked_work,
    )
    assert callable(get_last_activity_timestamp)
    assert callable(detect_untracked_work)
test("Activity monitor: all functions present", t1)

# Test 2: Activity monitor handles invalid paths
def t2():
    from src.services.verification.activity_monitor import get_last_activity_timestamp
    result = get_last_activity_timestamp("/nonexistent/path/12345")
    assert result is None
test("Activity monitor: handles invalid paths gracefully", t2)

# Test 3: Untracked work detection logic
def t3():
    from datetime import datetime, timedelta
    from src.services.verification.activity_monitor import detect_untracked_work

    # If last commit is after last activity, no untracked work
    result = detect_untracked_work(
        project_path="/tmp",
        last_commit_time=datetime.utcnow(),
        threshold_minutes=120,
    )
    assert result is None, "Should not detect untracked work when commit is recent"
test("Untracked work detection: no false positives with recent commits", t3)

# Test 4: Prompts module exists
def t4():
    from src.services.verification.prompts import (
        deliver_untracked_prompt,
        parse_notion_response,
    )
    assert callable(deliver_untracked_prompt)
    assert callable(parse_notion_response)
test("Prompts module: deliver + parse functions present", t4)

# Test 5: Notion response parsing
def t5():
    from src.services.verification.prompts import parse_notion_response

    # Test assign
    result = parse_notion_response("assign to AUTH-01")
    assert result["action"] == "assign"
    assert result["project_key"] == "AUTH-01"

    # Test ignore
    result = parse_notion_response("ignore this")
    assert result["action"] == "ignore"

    # Test no match
    result = parse_notion_response("random text")
    assert result is None
test("Notion response parsing: assign and ignore patterns work", t5)

# Test 6: Plan adjuster exists
def t6():
    from src.services.verification.plan_adjuster import (
        log_time_entry,
        adjust_remaining_hours,
        resolve_session,
    )
    assert callable(log_time_entry)
    assert callable(adjust_remaining_hours)
    assert callable(resolve_session)
test("Plan adjuster: all functions present", t6)

# Test 7: Verifier detects untracked sessions
def t7():
    from src.services.verification.verifier import (
        verify_today,
        verify_date,
        detect_untracked_sessions,
    )
    assert callable(verify_today)
    assert callable(verify_date)
    assert callable(detect_untracked_sessions)
test("Verifier: detect_untracked_sessions function present", t7)

# Test 8: ORM models for Phase 7.5
def t8():
    from src.models.database.models import UntrackedSession, TimeLog
    assert hasattr(UntrackedSession, 'project_id')
    assert hasattr(UntrackedSession, 'start_time')
    assert hasattr(UntrackedSession, 'end_time')
    assert hasattr(UntrackedSession, 'duration_minutes')
    assert hasattr(UntrackedSession, 'resolved')
    assert hasattr(TimeLog, 'project_id')
    assert hasattr(TimeLog, 'duration_minutes')
    assert hasattr(TimeLog, 'source')
    assert hasattr(TimeLog, 'task_type')
test("ORM: UntrackedSession + TimeLog models with all fields", t8)

# Test 9: CLI commands registered
def t9():
    from src.cli.main import cli
    commands = list(cli.commands.keys())
    assert 'untracked' in commands
test("CLI: untracked command registered", t9)

# Test 10: Untracked subcommands
def t10():
    from src.cli.commands.untracked import list_sessions, assign_session, ignore_session
    assert list_sessions.name == "list"
    assert assign_session.name == "assign"
    assert ignore_session.name == "ignore"
test("CLI: untracked list/assign/ignore subcommands", t10)

# Test 11: Migration file exists
def t11():
    import os
    m16 = os.path.join('migrations', '016_add_untracked_sessions.sql')
    assert os.path.exists(m16), f'Migration missing: {m16}'
    with open(m16) as f:
        content = f.read()
    assert 'CREATE TABLE IF NOT EXISTS untracked_sessions' in content
    assert 'CREATE TABLE IF NOT EXISTS time_logs' in content
    assert 'duration_minutes' in content
    assert 'resolved' in content
    assert 'source' in content
test("Migration: 016_add_untracked_sessions.sql correct", t11)

# Summary
print(f"\n{'='*40}")
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL PHASE 7.5 TESTS PASSED")
else:
    print("SOME TESTS FAILED")
    sys.exit(1)
