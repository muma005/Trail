"""Verification test for Phase 3: Progress Calculator & Report Generator."""
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

print("=== Phase 3 Verification Tests ===\n")

# Test 1: Progress calculator functions exist
def t1():
    from src.core.enrichment.progress_calculator import (
        calculate_simple_progress,
        calculate_weighted_progress,
        get_commit_stats,
        PRIORITY_WEIGHTS,
    )
    # Verify weights are correct
    assert PRIORITY_WEIGHTS["Critical"] == 3.0
    assert PRIORITY_WEIGHTS["Low"] == 0.5
    # Functions are callable (will return zeros without DB connection)
    assert callable(calculate_simple_progress)
    assert callable(calculate_weighted_progress)
    assert callable(get_commit_stats)
test("Progress calculator: simple, weighted, commit stats", t1)

# Test 2: Context Retriever exists
def t2():
    from src.services.report_generator.context_retriever import ContextRetriever
    retriever = ContextRetriever()
    assert hasattr(retriever, 'retrieve')
test("Context Retriever: retrieve method present", t2)

# Test 3: LLM Analyzer exists with prompt
def t3():
    from src.services.report_generator.llm_analyzer import LLMAnalyzer, REPORT_PROMPT_TEMPLATE
    analyzer = LLMAnalyzer(api_key="test")
    assert hasattr(analyzer, 'generate_report')
    assert hasattr(analyzer, 'generate_fallback_report')
    # Verify prompt enforces 6 sections and citation rules
    assert "6 sections" in REPORT_PROMPT_TEMPLATE.lower() or "exactly these 6 sections" in REPORT_PROMPT_TEMPLATE.lower()
    assert "SHA" in REPORT_PROMPT_TEMPLATE
    assert "do not invent" in REPORT_PROMPT_TEMPLATE.lower()
test("LLM Analyzer: methods present, prompt enforces citations", t3)

# Test 4: Validator extracts and validates SHAs
def t4():
    from src.services.report_generator.report_validator import Validator
    validator = Validator()

    # Test SHA extraction
    text = "Commit `abc123def45678901234567890123456` was made. Also see `aabbccdd`."
    shas = validator._extract_shas(text)
    assert "abc123def45678901234567890123456" in shas
    assert "aabbccdd" in shas

    # Test validation with valid context
    context = {"commits": [{"sha": "abc123def45678901234567890123456"}]}
    report = f"Commit abc123def45678901234567890123456 fixed the issue."
    validated, confidence, warnings = validator.validate(report, context)
    assert confidence == 100.0  # No invalid citations

    # Test validation with invalid SHA (valid hex but not in context)
    context = {"commits": [{"sha": "abc123def45678901234567890123456"}]}
    report = "Commit deadbeef00000000000000000000abcd was made."
    validated, confidence, warnings = validator.validate(report, context)
    assert confidence < 100.0  # Penalized
    assert len(warnings) > 0
test("Validator: SHA extraction + confidence penalty for invalid", t4)

# Test 5: Report Workflow exists
def t5():
    from src.services.report_generator.generator import ReportWorkflow
    workflow = ReportWorkflow(openrouter_api_key=None)
    assert hasattr(workflow, 'generate')
    assert hasattr(workflow, '_fallback_report')
test("Report Workflow: generate + fallback methods present", t5)

# Test 6: Fallback report generates 6 sections
def t6():
    from src.services.report_generator.llm_analyzer import LLMAnalyzer
    analyzer = LLMAnalyzer(api_key="")
    context = {
        "project": {"name": "Test", "key": "TST-01", "last_synced": None},
        "tasks": [
            {"title": "Task A", "status": "Done"},
            {"title": "Task B", "status": "In Progress"},
        ],
        "commits": [
            {"sha": "abc123def456", "message": "Fix bug", "date": "2025-01-01"},
        ],
        "latest_snapshot": None,
    }
    report = analyzer.generate_fallback_report(context)
    assert "# Resumption Report" in report
    assert "Progress Summary" in report
    assert "What Was Done" in report
    assert "What Needs To Be Done" in report
    assert "Confidence" in report or "LLM unavailable" in report
test("Fallback report: generates with all sections", t6)

# Test 7: Snapshot worker exists
def t7():
    from src.tasks.workers.snapshot_worker import create_daily_snapshots
    assert callable(create_daily_snapshots)
test("Snapshot Worker: create_daily_snapshots callable", t7)

# Test 8: ORM model ProjectSnapshot exists
def t8():
    from sqlalchemy import inspect as sa_inspect
    from src.models.database.models import ProjectSnapshot
    mapper = sa_inspect(ProjectSnapshot)
    col_names = [c.key for c in mapper.column_attrs]
    assert 'completion_percentage_simple' in col_names
    assert 'completion_percentage_weighted' in col_names
    assert 'total_tasks' in col_names
    assert 'completed_tasks' in col_names
test("ORM: ProjectSnapshot model with all fields", t8)

# Test 9: Settings has OpenRouter config
def t9():
    from src.config.settings import settings
    assert hasattr(settings, 'openrouter_api_key')
    assert hasattr(settings, 'openrouter_model')
    assert hasattr(settings, 'openrouter_timeout')
test("Settings: OpenRouter config (api_key, model, timeout)", t9)

# Test 10: CLI commands registered
def t10():
    from src.cli.main import cli
    commands = list(cli.commands.keys())
    assert 'progress' in commands
    assert 'report' in commands
test("CLI: progress and report commands registered", t10)

# Test 11: progress show subcommand
def t11():
    from src.cli.commands.progress import show
    assert show.name == "show"
test("CLI: progress show command", t11)

# Test 12: report generate subcommand
def t12():
    from src.cli.commands.report import generate
    assert generate.name == "generate"
    # Check it has --output option
    param_names = [p.name for p in generate.params]
    assert 'output' in param_names
test("CLI: report generate with --output option", t12)

# Test 13: Migration file exists
def t13():
    import os
    path = os.path.join('migrations', '006_add_project_snapshots.sql')
    assert os.path.exists(path), f'Migration missing: {path}'
    with open(path) as f:
        content = f.read()
    assert 'CREATE TABLE IF NOT EXISTS project_snapshots' in content
    assert 'completion_percentage_simple' in content
    assert 'completion_percentage_weighted' in content
test("Migration: 006_add_project_snapshots.sql correct", t13)

# Summary
print(f"\n{'='*40}")
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL PHASE 3 TESTS PASSED")
else:
    print("SOME TESTS FAILED")
    sys.exit(1)
