"""Verification test for Phase 6: Smart Work Planner Core."""
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

print("=== Phase 6 Verification Tests ===\n")

# Test 1: User profile loads
def t1():
    from src.services.work_planner.user_profile import UserProfile, get_user_profile
    profile = UserProfile()
    # Without DB it won't load but methods should exist
    assert hasattr(profile, 'work_start')
    assert hasattr(profile, 'work_end')
    assert hasattr(profile, 'max_parallel_projects')
    assert hasattr(profile, 'constant_project_id')
    assert hasattr(profile, 'deep_work_minutes')
    assert hasattr(profile, 'total_work_minutes')
test("User profile: all properties present", t1)

# Test 2: Scheduler functions exist
def t2():
    from src.services.work_planner.scheduler import (
        get_user_available_hours,
        get_project_urgency,
        allocate_hours,
    )
    assert callable(get_user_available_hours)
    assert callable(get_project_urgency)
    assert callable(allocate_hours)
test("Scheduler: all functions present", t2)

# Test 3: Urgency calculation
def t3():
    from datetime import date, timedelta
    from src.services.work_planner.scheduler import get_project_urgency

    class FakeConstraint:
        def __init__(self, deadline, priority):
            self.deadline = deadline
            self.priority = priority

    # Urgent deadline
    urgent = FakeConstraint(date.today() + timedelta(days=2), "Critical")
    # No deadline
    none = FakeConstraint(None, "Medium")

    u_urgent = get_project_urgency(urgent, date.today())
    u_none = get_project_urgency(none, date.today())

    assert u_urgent > u_none, f"Urgent ({u_urgent}) should be > no deadline ({u_none})"
test("Urgency: deadline projects get higher urgency", t3)

# Test 4: Task breaker exists
def t4():
    from src.services.task_breaker.breaker import break_into_work_units
    assert callable(break_into_work_units)

    # Test with mock data
    tasks = [
        {"id": "1", "title": "Quick fix", "estimated_minutes": 10, "size_tag": "quick", "priority": "Medium"},
        {"id": "2", "title": "Medium task", "estimated_minutes": 90, "size_tag": "medium", "priority": "High"},
        {"id": "3", "title": "Large refactor", "estimated_minutes": 300, "size_tag": "large", "priority": "Critical"},
    ]
    units = break_into_work_units(tasks, 120)
    assert len(units) > 0, "Should create at least one work unit"
test("Task breaker: break_into_work_units works", t4)

# Test 5: Task batching for quick tasks
def t5():
    from src.services.task_breaker.breaker import _batch_quick_tasks

    tasks = [
        {"title": "Fix typo", "estimated_minutes": 5, "project_id": "p1"},
        {"title": "Update docs", "estimated_minutes": 10, "project_id": "p1"},
        {"title": "Reply email", "estimated_minutes": 8, "project_id": "p1"},
    ]
    batches = _batch_quick_tasks(tasks, 30)
    assert len(batches) >= 1
    total = sum(b["estimated_minutes"] for b in batches)
    assert total == 23  # 5 + 10 + 8
test("Task batching: quick tasks batched correctly", t5)

# Test 6: Daily generator exists
def t6():
    from src.services.work_planner.daily_generator import generate_daily_plan
    assert callable(generate_daily_plan)
test("Daily generator: function present", t6)

# Test 7: ORM models for Phase 6
def t7():
    from src.models.database.models import ProjectConstraint, DailyPlan
    assert hasattr(ProjectConstraint, 'estimated_remaining_hours')
    assert hasattr(ProjectConstraint, 'deadline')
    assert hasattr(ProjectConstraint, 'priority')
    assert hasattr(ProjectConstraint, 'is_constant')
    assert hasattr(DailyPlan, 'plan_date')
    assert hasattr(DailyPlan, 'allocated_minutes')
    assert hasattr(DailyPlan, 'tasks_planned')
test("ORM: ProjectConstraint + DailyPlan models with all fields", t7)

# Test 8: CLI commands registered
def t8():
    from src.cli.main import cli
    commands = list(cli.commands.keys())
    assert 'plan' in commands
    # Project estimate and constraints are subcommands
    from src.cli.commands.project import set_estimate, show_constraints
    assert set_estimate.name == "estimate"
    assert show_constraints.name == "constraints"
test("CLI: plan command, project estimate/constraints registered", t8)

# Test 9: Plan today subcommand
def t9():
    from src.cli.commands.plan import plan_today
    assert plan_today.name == "today"
test("CLI: plan today command", t9)

# Test 10: Migration file exists
def t10():
    import os
    m10 = os.path.join('migrations', '010_add_planner_preferences.sql')
    assert os.path.exists(m10), f'Migration missing: {m10}'
    with open(m10) as f:
        content = f.read()
    assert 'max_parallel_projects' in content
    assert 'constant_project_id' in content
    assert 'deep_work_minutes' in content
    assert 'CREATE TABLE IF NOT EXISTS project_constraints' in content
    assert 'estimated_remaining_hours' in content
test("Migration: 010_add_planner_preferences.sql correct", t10)

# Summary
print(f"\n{'='*40}")
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL PHASE 6 TESTS PASSED")
else:
    print("SOME TESTS FAILED")
    sys.exit(1)
