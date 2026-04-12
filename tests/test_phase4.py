"""Verification test for Phase 4: Output Formats & Escalation Engine."""
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

print("=== Phase 4 Verification Tests ===\n")

# Test 1: Report format methods exist
def t1():
    from src.services.report_generator.generator import ReportWorkflow
    wf = ReportWorkflow(openrouter_api_key=None)
    assert hasattr(wf, 'format_report')
    assert hasattr(wf, '_format_json')
test("Report generator: format_report + _format_json methods", t1)

# Test 2: JSON output format generates valid JSON
def t2():
    import json
    from src.services.report_generator.generator import ReportWorkflow
    wf = ReportWorkflow(openrouter_api_key=None)
    context = {
        "project": {"name": "Test", "key": "TST-01", "last_synced": None},
        "tasks": [{"title": "A", "status": "Done"}],
        "commits": [{"sha": "abc123def456", "message": "Test", "date": "2025-01-01"}],
        "latest_snapshot": {"completion_simple": 50.0},
    }
    report = "## Header\nTest\n\n## Progress Summary\n50%\n\nConfidence: 80%"
    json_output = wf._format_json(context, report)
    parsed = json.loads(json_output)
    assert "project" in parsed
    assert "sections" in parsed
    assert "metadata" in parsed
    assert parsed["metadata"]["completion_percentage"] == 50.0
    assert parsed["metadata"]["confidence_score"] == 80
test("JSON format: generates valid JSON with sections + metadata", t2)

# Test 3: Escalation engine exists
def t3():
    from src.services.escalation.engine import EscalationEngine, check_stale_projects
    engine = EscalationEngine()
    assert hasattr(engine, 'check_stale_projects')
    assert hasattr(engine, '_send_warning')
    assert hasattr(engine, '_send_critical_alert')
    assert hasattr(engine, '_archive_project')
    assert hasattr(engine, '_post_notion_comment')
    assert hasattr(engine, '_send_slack_message')
    assert callable(check_stale_projects)
test("Escalation engine: all methods present", t3)

# Test 4: ORM models have Phase 4 columns
def t4():
    from src.models.database.models import Project, UserPreference
    # Project
    assert hasattr(Project, 'status')
    assert hasattr(Project, 'last_commit_date')
    assert hasattr(Project, 'last_warning_notified_at')
    assert hasattr(Project, 'last_critical_notified_at')
    # UserPreference
    assert hasattr(UserPreference, 'warning_days')
    assert hasattr(UserPreference, 'critical_days')
    assert hasattr(UserPreference, 'archive_days')
test("ORM: Project.status/last_commit_date/notification cols, UserPreference thresholds", t4)

# Test 5: Settings has Slack webhook config
def t5():
    from src.config.settings import settings
    assert hasattr(settings, 'slack_webhook_url')
test("Settings: slack_webhook_url present", t5)

# Test 6: CLI commands registered
def t6():
    from src.cli.main import cli
    commands = list(cli.commands.keys())
    assert 'dashboard' in commands
    assert 'project' in commands
test("CLI: dashboard + project commands registered", t6)

# Test 7: project archive/resurrect subcommands
def t7():
    from src.cli.commands.project import archive_project, resurrect_project
    assert archive_project.name == "archive"
    assert resurrect_project.name == "resurrect"
test("CLI: project archive/resurrect subcommands", t7)

# Test 8: report generate has --format option
def t8():
    from src.cli.commands.report import generate
    param_names = [p.name for p in generate.params]
    assert 'fmt' in param_names  # --format maps to fmt
test("CLI: report generate has --format option", t8)

# Test 9: Migration files exist
def t9():
    import os
    m7 = os.path.join('migrations', '007_add_abandonment_thresholds.sql')
    assert os.path.exists(m7), f'Migration missing: {m7}'
    with open(m7) as f:
        content = f.read()
    assert 'warning_days' in content
    assert 'critical_days' in content
    assert 'archive_days' in content
    assert "status VARCHAR(20) DEFAULT 'active'" in content
    assert 'last_commit_date' in content
    assert 'last_warning_notified_at' in content
test("Migration: 007_add_abandonment_thresholds.sql correct", t9)

# Test 10: Dashboard file exists and has key components
def t10():
    import os
    dash_path = os.path.join('src', 'dashboard.py')
    assert os.path.exists(dash_path), f'Dashboard missing: {dash_path}'
    with open(dash_path) as f:
        content = f.read()
    assert 'st.set_page_config' in content
    assert 'load_projects' in content
    assert 'load_snapshots' in content
    assert 'st.line_chart' in content  # Progress chart
test("Dashboard: Streamlit app exists with key components", t10)

# Summary
print(f"\n{'='*40}")
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL PHASE 4 TESTS PASSED")
else:
    print("SOME TESTS FAILED")
    sys.exit(1)
