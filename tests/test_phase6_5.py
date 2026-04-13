"""Verification test for Phase 6.5: Enhanced Planner."""
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

print("=== Phase 6.5 Verification Tests ===\n")

# Test 1: Google Calendar client exists
def t1():
    from src.integrations.calendar.google_calendar import GoogleCalendarClient
    client = GoogleCalendarClient()
    assert hasattr(client, 'fetch_events')
    assert hasattr(client, 'get_busy_slots_for_date')
    assert hasattr(client, 'authenticate')
test("Google Calendar client: all methods present", t1)

# Test 2: Holiday manager functions exist
def t2():
    from src.services.work_planner.holiday_manager import (
        is_time_off,
        add_time_off,
        remove_time_off,
        list_time_off,
    )
    assert callable(is_time_off)
    assert callable(add_time_off)
    assert callable(remove_time_off)
    assert callable(list_time_off)
test("Holiday manager: all functions present", t2)

# Test 3: Switch cost functions exist
def t3():
    from src.services.work_planner.context_switch import (
        get_switch_penalty,
        set_switch_cost,
    )
    assert callable(get_switch_penalty)
    assert callable(set_switch_cost)
test("Switch costs: get_switch_penalty + set_switch_cost present", t3)

# Test 4: Dependency graph builder exists
def t4():
    from src.core.enrichment.dependency_graph import (
        build_dependency_graph,
        topological_sort_tasks,
        get_cross_project_warnings,
    )
    assert callable(build_dependency_graph)
    assert callable(topological_sort_tasks)
    assert callable(get_cross_project_warnings)
test("Dependency graph: all functions present", t4)

# Test 5: Topological sort works
def t5():
    from src.core.enrichment.dependency_graph import topological_sort_tasks

    graph = {
        "task_b": ["task_a"],  # B depends on A
        "task_a": [],
        "task_c": ["task_b"],  # C depends on B
    }
    tasks = [
        {"id": "task_a", "title": "A", "priority": "Medium"},
        {"id": "task_b", "title": "B", "priority": "High"},
        {"id": "task_c", "title": "C", "priority": "Critical"},
    ]
    sorted_tasks = topological_sort_tasks(tasks, graph)

    # A must come before B, B must come before C
    order = {t["id"]: i for i, t in enumerate(sorted_tasks)}
    assert order["task_a"] < order["task_b"], "A should come before B"
    assert order["task_b"] < order["task_c"], "B should come before C"
test("Topological sort: respects dependencies", t5)

# Test 6: Cycle detection works
def t6():
    from src.core.enrichment.dependency_graph import _detect_and_break_cycles

    graph = {
        "a": ["b"],
        "b": ["c"],
        "c": ["a"],  # Cycle: a → b → c → a
    }
    clean_graph, broken = _detect_and_break_cycles(graph)
    assert len(broken) > 0, "Should detect at least one cycle"
test("Cycle detection: detects and breaks cycles", t6)

# Test 7: ORM models for Phase 6.5
def t7():
    from src.models.database.models import UserTimeOff, SwitchCost
    assert hasattr(UserTimeOff, 'start_date')
    assert hasattr(UserTimeOff, 'end_date')
    assert hasattr(UserTimeOff, 'reason')
    assert hasattr(SwitchCost, 'from_project_id')
    assert hasattr(SwitchCost, 'to_project_id')
    assert hasattr(SwitchCost, 'penalty_minutes')
test("ORM: UserTimeOff + SwitchCost models with all fields", t7)

# Test 8: CLI commands registered
def t8():
    from src.cli.main import cli
    commands = list(cli.commands.keys())
    assert 'timeoff' in commands
    assert 'switch-cost' in commands
test("CLI: timeoff + switch-cost commands registered", t8)

# Test 9: Plan today accepts new flags
def t9():
    from src.cli.commands.plan import plan_today
    param_names = [p.name for p in plan_today.params]
    assert 'detail' in param_names
    assert 'with_deps' in param_names
    assert 'calendar' in param_names
test("CLI: plan today has --detail, --with-deps, --calendar flags", t9)

# Test 10: Migration file exists
def t10():
    import os
    m13 = os.path.join('migrations', '013_add_user_time_off.sql')
    assert os.path.exists(m13), f'Migration missing: {m13}'
    with open(m13) as f:
        content = f.read()
    assert 'CREATE TABLE IF NOT EXISTS user_time_off' in content
    assert 'CREATE TABLE IF NOT EXISTS switch_costs' in content
    assert 'penalty_minutes' in content
test("Migration: 013_add_user_time_off.sql correct", t10)

# Summary
print(f"\n{'='*40}")
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL PHASE 6.5 TESTS PASSED")
else:
    print("SOME TESTS FAILED")
    sys.exit(1)
