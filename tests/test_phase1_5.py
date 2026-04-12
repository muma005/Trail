"""Verification test for Phase 1.5: Scope filtering + commit parsing."""
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

print("=== Phase 1.5 Verification Tests ===\n")

# Test 1: Commit parser patterns
def t1():
    from src.core.enrichment.commit_parser import parse_task_id, classify_commit
    # Task patterns
    assert parse_task_id("Add login [TASK-42]") == "TASK-42"
    assert parse_task_id("Fix bug #123") == "#123"
    assert parse_task_id("fixes #789") == "#789"
    assert parse_task_id("closes #456") == "#456"
    # No match
    assert parse_task_id("Update docs") is None
    assert parse_task_id("WIP: refactor auth") is None
    assert parse_task_id("") is None
    # Classification
    assert classify_commit("Update docs") is True
    assert classify_commit("Add [AUTH-01]") is False
test("Commit parser: all regex patterns + classification", t1)

# Test 2: GitHub connector has fetch_filtered_commits
def t2():
    from src.core.connectors.github_connector import GitHubConnector
    assert hasattr(GitHubConnector, 'fetch_filtered_commits')
    assert hasattr(GitHubConnector, '_matches_path_filter')
    # Test path filter logic
    connector = GitHubConnector.__new__(GitHubConnector)
    files = [{"filename": "src/auth/login.py", "additions": 10, "deletions": 2}]
    assert connector._matches_path_filter(files, ["src/auth/"]) is True
    assert connector._matches_path_filter(files, ["docs/"]) is False
    assert connector._matches_path_filter([], ["src/"]) is False
test("GitHub connector: fetch_filtered_commits + path filter logic", t2)

# Test 3: ORM models have Phase 1.5 fields
def t3():
    from src.models.database.models import Project, Commit, ProjectScope
    # Project has scopes relationship
    assert hasattr(Project, 'scopes')
    # Commit has parsing fields
    assert hasattr(Commit, 'parsed_task_id')
    assert hasattr(Commit, 'needs_classification')
    # ProjectScope model exists
    assert hasattr(ProjectScope, 'scope_type')
    assert hasattr(ProjectScope, 'scope_value')
test("ORM models: Project.scopes, Commit.parsed_task_id, ProjectScope", t3)

# Test 4: DB session has Phase 1.5 functions
def t4():
    from src.models.database import session
    assert hasattr(session, 'save_project_scopes')
    assert hasattr(session, 'get_project_scopes')
    assert hasattr(session, 'get_orphan_commits')
test("DB functions: save_project_scopes, get_project_scopes, get_orphan_commits", t4)

# Test 5: CLI commands registered
def t5():
    from src.cli.main import cli
    commands = list(cli.commands.keys())
    assert 'project' in commands
    assert 'sync' in commands
    assert 'orphans' in commands
test("CLI commands: project, sync, orphans all registered", t5)

# Test 6: project add accepts --branch and --path
def t6():
    from src.cli.commands.project import add_project
    params = {p.name for p in add_project.params}
    assert 'branch' in params, f"branch not in {params}"
    assert 'paths' in params, f"paths not in {params}"
test("CLI: project add has --branch and --path options", t6)

# Test 7: Migration file exists
def t7():
    import os
    path = os.path.join('migrations', '002_add_project_scopes_and_commit_parsing.sql')
    assert os.path.exists(path), f'Migration missing: {path}'
    with open(path) as f:
        content = f.read()
    assert 'CREATE TABLE IF NOT EXISTS project_scopes' in content
    assert 'parsed_task_id' in content
    assert 'needs_classification' in content
test("Migration SQL: 002_add_project_scopes_and_commit_parsing.sql", t7)

# Test 8: Path filter edge cases
def t8():
    from src.core.connectors.github_connector import GitHubConnector
    c = GitHubConnector.__new__(GitHubConnector)
    # Multiple files, one matches
    files = [
        {"filename": "README.md", "additions": 1},
        {"filename": "src/auth/jwt.py", "additions": 5},
    ]
    assert c._matches_path_filter(files, ["src/auth/"]) is True
    # None match
    assert c._matches_path_filter(files, ["docs/", "tests/"]) is False
    # Empty paths = no filter (function not called, but logic holds)
    assert c._matches_path_filter(files, []) is False
test("Path filter: multiple files, partial matches, no matches", t8)

# Summary
print(f"\n{'='*40}")
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL PHASE 1.5 TESTS PASSED")
else:
    print("SOME TESTS FAILED")
    sys.exit(1)
