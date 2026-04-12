"""Quick verification test for Phase 0 + Phase 1 without requiring DB."""
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

print("=== Phase 0 + 1 Verification Tests ===\n")

# Test 1: CLI loads and registers all commands
def t1():
    from src.cli.main import cli
    commands = list(cli.commands.keys())
    assert 'project' in commands, 'project command missing'
    assert 'sync' in commands, 'sync command missing'
test("CLI commands registered (project, sync)", t1)

# Test 2: Exception hierarchy
def t2():
    from src.utils.exceptions.base import (
        TrailError, ValidationError, GitHubError,
        NotionError, DatabaseError, DuplicateProjectError
    )
    e = DuplicateProjectError('test')
    assert isinstance(e, DatabaseError)
    assert isinstance(e, TrailError)
test("Exception hierarchy correct", t2)

# Test 3: Redis cache graceful fallback
def t3():
    from src.utils.helpers.cache import cache
    result = cache.get('test:key:never:exists')
    assert result is None  # No Redis running, should return None gracefully
test("Redis cache graceful fallback (no Redis)", t3)

# Test 4: ORM models have Phase 0 + 1 attributes
def t4():
    from src.models.database.models import Project, Commit, UserPreference, SyncLog
    # Phase 0
    assert hasattr(Project, 'project_key')
    assert hasattr(Project, 'github_repo_url')
    assert hasattr(Project, 'notion_database_id')
    # Phase 1
    assert hasattr(Project, 'last_synced_at'), 'Phase 1 column missing'
    assert hasattr(Commit, 'commit_sha'), 'Commit model broken'
    assert hasattr(Commit, 'files_changed'), 'files_changed column missing'
    assert hasattr(Commit, 'lines_added')
    assert hasattr(Commit, 'lines_deleted')
test("ORM models correct (Project + Commit with Phase 1 fields)", t4)

# Test 5: GitHub connector has Phase 1 methods
def t5():
    from src.core.connectors.github_connector import GitHubConnector
    assert hasattr(GitHubConnector, 'fetch_commits'), 'fetch_commits missing'
    assert hasattr(GitHubConnector, '_check_rate_limit'), 'rate limit check missing'
    assert hasattr(GitHubConnector, '_fetch_with_retry'), 'retry logic missing'
    assert hasattr(GitHubConnector, '_parse_commit'), 'parse_commit missing'
test("GitHub connector has all Phase 1 methods", t5)

# Test 6: DB session has all Phase 1 functions
def t6():
    from src.models.database import session
    assert hasattr(session, 'store_commits'), 'store_commits missing'
    assert hasattr(session, 'get_project_by_key'), 'get_project_by_key missing'
    assert hasattr(session, 'update_last_synced'), 'update_last_synced missing'
    assert hasattr(session, 'get_commit_count'), 'get_commit_count missing'
    assert hasattr(session, 'get_existing_commit_shas'), 'get_existing_commit_shas missing'
test("All Phase 1 DB functions present", t6)

# Test 7: Input validators
def t7():
    from src.utils.helpers.validators import (
        validate_github_url, validate_notion_database_id,
        validate_project_key, validate_project_name
    )
    # Valid
    assert validate_github_url('https://github.com/octocat/Hello-World') == 'https://github.com/octocat/Hello-World'
    assert validate_github_url('octocat/Hello-World') == 'https://github.com/octocat/Hello-World'
    assert validate_notion_database_id('abcdef123456abcdef123456abcdef12') == 'abcdef123456abcdef123456abcdef12'
    assert validate_project_key('AUTH-01') == 'AUTH-01'
    assert validate_project_name('Auth Service') == 'Auth Service'
    # Invalid
    from src.utils.exceptions.base import ValidationError
    try:
        validate_github_url('not-a-url')
        assert False, 'Should have raised'
    except ValidationError:
        pass
    try:
        validate_notion_database_id('short')
        assert False, 'Should have raised'
    except ValidationError:
        pass
    try:
        validate_project_key('invalid key!')
        assert False, 'Should have raised'
    except ValidationError:
        pass
test("Input validators (valid + invalid cases)", t7)

# Test 8: Migration file exists
def t8():
    import os
    path = os.path.join('migrations', '001_add_commits_and_last_synced.sql')
    assert os.path.exists(path), f'Migration file missing: {path}'
    with open(path) as f:
        content = f.read()
    assert 'CREATE TABLE IF NOT EXISTS commits' in content, 'commits table SQL missing'
    assert 'last_synced_at' in content, 'last_synced_at column SQL missing'
test("Migration SQL file exists with correct content", t8)

# Summary
print(f"\n{'='*40}")
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL TESTS PASSED")
else:
    print("SOME TESTS FAILED")
    sys.exit(1)
