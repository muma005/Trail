"""Verification test for Phase 10: Cross-Project Orchestration & Scaling."""
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

print("=== Phase 10 Verification Tests ===\n")

# Test 1: Global scheduler exists
def t1():
    from src.services.work_planner.global_scheduler import GlobalScheduler, get_global_scheduler
    scheduler = get_global_scheduler()
    assert hasattr(scheduler, 'build_graph')
    assert hasattr(scheduler, 'get_topological_order')
    assert hasattr(scheduler, 'compute_critical_path')
    assert hasattr(scheduler, 'get_global_backlog')
    assert hasattr(scheduler, 'generate_leveled_plan')
test("Global scheduler: all methods present", t1)

# Test 2: Planner integration functions
def t2():
    from src.services.work_planner.planner import (
        get_critical_path,
        get_global_backlog,
        get_leveled_plan,
    )
    assert callable(get_critical_path)
    assert callable(get_global_backlog)
    assert callable(get_leveled_plan)
test("Planner: critical path, backlog, leveled plan functions", t2)

# Test 3: Planner tools for AI Brain
def t3():
    from src.ai.tools.planner_tools import get_global_backlog_tool, get_critical_path_tool
    backlog_tool = get_global_backlog_tool()
    critical_tool = get_critical_path_tool()
    assert backlog_tool['function']['name'] == 'get_global_backlog'
    assert critical_tool['function']['name'] == 'get_critical_path'
    assert callable(backlog_tool['execute'])
    assert callable(critical_tool['execute'])
test("AI Brain tools: global_backlog and critical_path tools", t3)

# Test 4: CLI plan commands
def t4():
    from src.cli.commands.plan import critical_path, global_backlog
    assert critical_path.name == "critical-path"
    assert global_backlog.name == "global-backlog"
test("CLI: plan critical-path and global-backlog commands", t4)

# Test 5: networkx imported successfully
def t5():
    import networkx as nx
    assert hasattr(nx, 'DiGraph')
    assert hasattr(nx, 'topological_sort')
    assert hasattr(nx, 'dag_longest_path')
test("networkx: imported with required functions", t5)

# Test 6: Migration file exists
def t6():
    import os
    assert os.path.exists('requirements.txt')
    with open('requirements.txt') as f:
        content = f.read()
    assert 'networkx' in content
test("requirements.txt: networkx included", t6)

# Test 7: FINAL_INTEGRATION.md exists
def t7():
    import os
    assert os.path.exists('FINAL_INTEGRATION.md')
    with open('FINAL_INTEGRATION.md') as f:
        content = f.read()
    assert 'Quick Start' in content
    assert 'Testing Plan' in content
    assert 'Success Criteria' in content
test("FINAL_INTEGRATION.md: exists with required sections", t7)

# Summary
print(f"\n{'='*40}")
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL PHASE 10 TESTS PASSED")
else:
    print("SOME TESTS FAILED")
    sys.exit(1)
