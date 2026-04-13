"""Verification test for Phase 7: Verification & Auto-Reassignment."""
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

print("=== Phase 7 Verification Tests ===\n")

# Test 1: Partial progress detection
def t1():
    from src.services.verification.partial_progress import detect_partial_progress

    # Complete task
    result = detect_partial_progress(
        {"status": "Done", "progress_percentage": None},
        [],
        []
    )
    assert result["was_completed"] is True
    assert result["progress_percentage"] == 100.0

    # No progress
    result = detect_partial_progress(
        {"status": "Not Started", "progress_percentage": None},
        [],
        []
    )
    assert result["was_completed"] is False
    assert result["progress_percentage"] == 0.0

    # Commit heuristic
    result = detect_partial_progress(
        {"status": "In Progress", "progress_percentage": None},
        [{"sha": "abc123"}],
        []
    )
    assert result["progress_percentage"] == 30.0
    assert result["detection_method"] == "commits"

    # Sub-task ratio
    result = detect_partial_progress(
        {"status": "In Progress", "progress_percentage": None},
        [],
        [{"is_completed": True}, {"is_completed": False}, {"is_completed": True}]
    )
    assert abs(result["progress_percentage"] - 66.67) < 1.0
    assert result["detection_method"] == "subtasks"

    # Notion progress field
    result = detect_partial_progress(
        {"status": "In Progress", "progress_percentage": 45},
        [],
        []
    )
    assert result["progress_percentage"] == 45.0
    assert result["detection_method"] == "status"
test("Partial progress: all detection methods work", t1)

# Test 2: Remaining estimation
def t2():
    from src.services.verification.auto_reassignment import estimate_remaining

    assert estimate_remaining(60, 0) == 60  # No progress
    assert estimate_remaining(60, 100) == 0  # Complete
    assert estimate_remaining(60, 50) == 30  # Half done
    assert estimate_remaining(120, 30) == 84  # 30% done
test("Remaining estimation: correct calculations", t2)

# Test 3: Verification worker exists
def t3():
    from src.services.verification.verifier import verify_today, verify_date
    assert callable(verify_today)
    assert callable(verify_date)
test("Verification worker: verify_today + verify_date present", t3)

# Test 4: Auto-reassignment exists
def t4():
    from src.services.verification.auto_reassignment import run_reassignment
    assert callable(run_reassignment)
test("Auto-reassignment: run_reassignment present", t4)

# Test 5: ORM model exists
def t5():
    from src.models.database.models import PlannedTaskVerification
    assert hasattr(PlannedTaskVerification, 'daily_plan_id')
    assert hasattr(PlannedTaskVerification, 'task_id')
    assert hasattr(PlannedTaskVerification, 'was_completed')
    assert hasattr(PlannedTaskVerification, 'partial_progress_percentage')
    assert hasattr(PlannedTaskVerification, 'remaining_estimate_minutes')
    assert hasattr(PlannedTaskVerification, 'detection_method')
    assert hasattr(PlannedTaskVerification, 'missed_reason')
    assert hasattr(PlannedTaskVerification, 'reassigned_to_plan_id')
test("ORM: PlannedTaskVerification model with all fields", t5)

# Test 6: CLI commands registered
def t6():
    from src.cli.main import cli
    commands = list(cli.commands.keys())
    assert 'verify' in commands
    assert 'reassign' in commands
test("CLI: verify + reassign commands registered", t6)

# Test 7: Verify subcommands
def t7():
    from src.cli.commands.verify import verify_today, verify_date_cmd
    assert verify_today.name == "today"
    assert verify_date_cmd.name == "date"
test("CLI: verify today + verify date subcommands", t7)

# Test 8: Reassign subcommands
def t8():
    from src.cli.commands.reassign import reassign_preview, reassign_apply
    assert reassign_preview.name == "preview"
    assert reassign_apply.name == "apply"
test("CLI: reassign preview + apply subcommands", t8)

# Test 9: Migration file exists
def t9():
    import os
    m15 = os.path.join('migrations', '015_create_planned_task_verification.sql')
    assert os.path.exists(m15), f'Migration missing: {m15}'
    with open(m15) as f:
        content = f.read()
    assert 'CREATE TABLE IF NOT EXISTS planned_task_verification' in content
    assert 'partial_progress_percentage' in content
    assert 'remaining_estimate_minutes' in content
    assert 'detection_method' in content
test("Migration: 015_create_planned_task_verification.sql correct", t9)

# Summary
print(f"\n{'='*40}")
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL PHASE 7 TESTS PASSED")
else:
    print("SOME TESTS FAILED")
    sys.exit(1)
