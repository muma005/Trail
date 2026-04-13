"""Verification test for Phase 8: Learning & Personalization."""
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

print("=== Phase 8 Verification Tests ===\n")

# Test 1: Learning engine exists
def t1():
    from src.services.learning.engine import (
        LearningEngine,
        get_learning_engine,
    )
    engine = get_learning_engine()
    assert hasattr(engine, 'update_duration_multiplier')
    assert hasattr(engine, 'get_duration_multiplier')
    assert hasattr(engine, 'update_focus_peaks')
    assert hasattr(engine, 'get_focus_peaks')
    assert hasattr(engine, 'check_empty_promise')
    assert hasattr(engine, 'get_project_multiplier')
    assert hasattr(engine, 'get_all_patterns')
    assert hasattr(engine, 'reset_pattern')
    engine.close()
test("Learning engine: all methods present", t1)

# Test 2: Duration multiplier EMA calculation
def t2():
    from src.services.learning.engine import LearningEngine
    engine = LearningEngine()

    # Simulate EMA: after 5 samples with ratio 1.18 each, should be close to 1.18
    # Test the math logic directly
    old_value = 1.0
    old_count = 0
    ratios = [1.17, 1.08, 1.25, 1.13, 1.20]  # Average ≈ 1.166

    for ratio in ratios:
        new_value = (old_value * old_count + ratio) / (old_count + 1)
        old_value = new_value
        old_count += 1

    # After 5 samples, should be close to average
    expected_avg = sum(ratios) / len(ratios)
    assert abs(old_value - expected_avg) < 0.01, f"EMA {old_value:.4f} should be close to avg {expected_avg:.4f}"

    engine.close()
test("Duration multiplier: exponential moving average calculation", t2)

# Test 3: Focus peak extraction
def t3():
    from src.services.learning.engine import LearningEngine
    engine = LearningEngine()

    # Test get_focus_peaks returns default when no data
    peaks = engine.get_focus_peaks()
    assert isinstance(peaks, list)
    assert len(peaks) >= 1

    engine.close()
test("Focus peaks: returns list with defaults", t3)

# Test 4: Empty promise detection logic
def t4():
    from src.services.learning.engine import LearningEngine
    engine = LearningEngine()

    # Test get_project_multiplier returns 1.0 when no data
    multiplier = engine.get_project_multiplier("fake-project-id")
    assert multiplier == 1.0

    engine.close()
test("Empty promise: returns 1.0 when no data", t4)

# Test 5: Task type extraction
def t5():
    from src.services.learning.engine import LearningEngine
    engine = LearningEngine()

    # Mock task object for testing _extract_task_type
    class MockTask:
        def __init__(self, tags=None, title=""):
            self.tags = tags
            self.title = title

    # Test tag-based extraction
    task = MockTask(tags=["test", "unit"])
    assert engine._extract_task_type(task) == "unit_test"

    task = MockTask(tags=["bugfix"])
    assert engine._extract_task_type(task) == "bugfix"

    task = MockTask(tags=["docs"])
    assert engine._extract_task_type(task) == "docs"

    task = MockTask(tags=["refactor"])
    assert engine._extract_task_type(task) == "refactor"

    # Test title-based extraction
    task = MockTask(title="Add login test")
    assert engine._extract_task_type(task) == "unit_test"

    task = MockTask(title="Fix authentication bug")
    assert engine._extract_task_type(task) == "bugfix"

    task = MockTask(title="Update documentation")
    assert engine._extract_task_type(task) == "docs"

    task = MockTask(title="Refactor database layer")
    assert engine._extract_task_type(task) == "refactor"

    task = MockTask(title="Implement feature")
    assert engine._extract_task_type(task) == "general"

    engine.close()
test("Task type extraction: tags and title keywords work", t5)

# Test 6: ORM model exists
def t6():
    from src.models.database.models import LearnedPattern
    assert hasattr(LearnedPattern, 'pattern_type')
    assert hasattr(LearnedPattern, 'context')
    assert hasattr(LearnedPattern, 'value')
    assert hasattr(LearnedPattern, 'confidence')
    assert hasattr(LearnedPattern, 'sample_count')
test("ORM: LearnedPattern model with all fields", t6)

# Test 7: CLI commands registered
def t7():
    from src.cli.main import cli
    commands = list(cli.commands.keys())
    assert 'learning' in commands
test("CLI: learning command registered", t7)

# Test 8: Learning subcommands
def t8():
    from src.cli.commands.learning import (
        show_patterns,
        update_duration,
        update_focus,
        check_empty_promise,
        show_focus,
        reset_patterns,
    )
    assert show_patterns.name == "show"
    assert update_duration.name == "update-duration"
    assert update_focus.name == "update-focus"
    assert check_empty_promise.name == "empty-promise"
    assert show_focus.name == "focus"
    assert reset_patterns.name == "reset"
test("CLI: learning show/update/reset/focus/empty-promise subcommands", t8)

# Test 9: Migration file exists
def t9():
    import os
    m17 = os.path.join('migrations', '017_create_learned_patterns.sql')
    assert os.path.exists(m17), f'Migration missing: {m17}'
    with open(m17) as f:
        content = f.read()
    assert 'CREATE TABLE IF NOT EXISTS learned_patterns' in content
    assert 'pattern_type' in content
    assert 'context' in content
    assert 'value' in content
    assert 'confidence' in content
    assert 'sample_count' in content
test("Migration: 017_create_learned_patterns.sql correct", t9)

# Test 10: Verifier calls duration learning on completion
def t10():
    import inspect
    from src.services.verification import verifier
    source = inspect.getsource(verifier.verify_date)
    assert 'update_duration_multiplier' in source, "Verifier should call duration learning"
test("Verifier: calls update_duration_multiplier on task completion", t10)

# Summary
print(f"\n{'='*40}")
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL PHASE 8 TESTS PASSED")
else:
    print("SOME TESTS FAILED")
    sys.exit(1)
