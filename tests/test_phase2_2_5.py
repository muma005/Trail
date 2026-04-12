"""Verification test for Phase 2 & 2.5: Notion sync, linking, dependencies, sub-tasks."""
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

print("=== Phase 2 & 2.5 Verification Tests ===\n")

# Test 1: Notion connector has all required methods
def t1():
    from src.core.connectors.notion_connector import NotionConnector
    assert hasattr(NotionConnector, 'fetch_database_pages')
    assert hasattr(NotionConnector, 'fetch_page_blocks')
    assert hasattr(NotionConnector, '_parse_page')
    assert hasattr(NotionConnector, '_extract_title')
    assert hasattr(NotionConnector, '_extract_select')
    assert hasattr(NotionConnector, '_extract_relations')
    assert hasattr(NotionConnector, '_extract_estimate')
test("Notion connector: all methods present", t1)

# Test 2: Embedding helper loads
def t2():
    from src.core.enrichment.embedding_generator import embedder
    # Should not crash even if sentence-transformers not installed
    assert hasattr(embedder, 'is_available')
    assert hasattr(embedder, 'cosine_similarity')
    assert hasattr(embedder, 'find_suggestions')
test("Embedding helper: loads gracefully", t2)

# Test 3: Commit linker exists
def t3():
    from src.core.enrichment.linker import CommitLinker
    linker = CommitLinker()
    assert hasattr(linker, 'exact_match_links')
    assert hasattr(linker, 'generate_embedding_suggestions')
test("Commit linker: exact_match_links + generate_embedding_suggestions", t3)

# Test 4: Size classification logic
def t4():
    from src.core.enrichment.normalizer import classify_size
    # Estimate-based
    assert classify_size({"estimated_minutes": 10}) == "quick"
    assert classify_size({"estimated_minutes": 60}) == "medium"
    assert classify_size({"estimated_minutes": 300}) == "large"
    # Keyword-based
    assert classify_size({"title": "Quick fix"}) == "quick"
    assert classify_size({"title": "Large refactor"}) == "large"
    assert classify_size({"title": "Normal task"}) == "medium"
test("Size classifier: estimate-based + keyword-based", t4)

# Test 5: Dependency extraction
def t5():
    from src.core.enrichment.normalizer import extract_dependencies
    page_map = {"abc123": "task-A", "def456": "task-B"}
    task = {
        "id": "task-A",
        "relations": {
            "Blocked by": ["def456"],
            "Blocks": [],
        }
    }
    deps = extract_dependencies(task, page_map)
    assert len(deps) == 1
    assert deps[0]["task_id"] == "task-A"
    assert deps[0]["depends_on_task_id"] == "task-B"
    assert deps[0]["dependency_type"] == "blocked_by"
test("Dependency extraction: Blocked by relations", t5)

# Test 6: Sub-task extraction from to_do blocks
def t6():
    from src.core.enrichment.subtask_aggregator import extract_subtasks_from_blocks
    blocks = [
        {
            "type": "to_do",
            "to_do": {
                "rich_text": [{"plain_text": "Write tests"}],
                "checked": True,
            }
        },
        {
            "type": "to_do",
            "to_do": {
                "rich_text": [{"plain_text": "Update docs"}],
                "checked": False,
            }
        },
        {"type": "paragraph", "paragraph": {}},  # Not a to_do, should be skipped
    ]
    subtasks = extract_subtasks_from_blocks(blocks)
    assert len(subtasks) == 2
    assert subtasks[0]["title"] == "Write tests"
    assert subtasks[0]["is_completed"] is True
    assert subtasks[1]["title"] == "Update docs"
    assert subtasks[1]["is_completed"] is False
test("Sub-task extraction: to_do blocks parsed correctly", t6)

# Test 7: ORM models for Phase 2 + 2.5
def t7():
    from src.models.database.models import (
        NotionTask, CommitTaskLink, TaskDependency, SubTask
    )
    # NotionTask fields
    assert hasattr(NotionTask, 'notion_page_id')
    assert hasattr(NotionTask, 'size_tag')
    assert hasattr(NotionTask, 'sub_tasks')
    assert hasattr(NotionTask, 'dependencies')
    # CommitTaskLink
    assert hasattr(CommitTaskLink, 'confidence')
    assert hasattr(CommitTaskLink, 'is_suggestion')
    # TaskDependency
    assert hasattr(TaskDependency, 'depends_on_task_id')
    assert hasattr(TaskDependency, 'depends_on_project_id')
    # SubTask
    assert hasattr(SubTask, 'parent_task_id')
    assert hasattr(SubTask, 'is_completed')
test("ORM models: NotionTask, CommitTaskLink, TaskDependency, SubTask", t7)

# Test 8: DB functions for Phase 2 + 2.5
def t8():
    from src.models.database import session
    assert hasattr(session, 'store_notion_tasks')
    assert hasattr(session, 'get_notion_tasks')
    assert hasattr(session, 'create_commit_link')
    assert hasattr(session, 'get_link_suggestions')
    assert hasattr(session, 'accept_suggestion')
    assert hasattr(session, 'ignore_suggestion')
    assert hasattr(session, 'store_dependencies')
    assert hasattr(session, 'store_subtasks')
    assert hasattr(session, 'update_task_size_tags')
    assert hasattr(session, 'get_task_details')
test("DB functions: all Phase 2 + 2.5 functions present", t8)

# Test 9: CLI commands registered
def t9():
    from src.cli.main import cli
    commands = list(cli.commands.keys())
    assert 'project' in commands
    assert 'sync' in commands
    assert 'link' in commands
    assert 'task' in commands
    assert 'orphans' in commands
test("CLI commands: project, sync, link, task, orphans", t9)

# Test 10: link subcommands
def t10():
    from src.cli.commands.link import suggestions, accept, ignore
    assert suggestions.name == "suggestions"
    assert accept.name == "accept"
    assert ignore.name == "ignore"
test("CLI: link suggestions/accept/ignore commands", t10)

# Test 11: task show command
def t11():
    from src.cli.commands.task import show
    assert show.name == "show"
test("CLI: task show command", t11)

# Test 12: Migration files exist
def t12():
    import os
    m3 = os.path.join('migrations', '003_add_notion_tables.sql')
    m4 = os.path.join('migrations', '004_add_dependencies_and_subtasks.sql')
    assert os.path.exists(m3), f'Migration missing: {m3}'
    assert os.path.exists(m4), f'Migration missing: {m4}'
    with open(m3) as f:
        c3 = f.read()
    with open(m4) as f:
        c4 = f.read()
    assert 'CREATE TABLE IF NOT EXISTS notion_tasks' in c3
    assert 'CREATE TABLE IF NOT EXISTS commit_task_links' in c3
    assert 'CREATE TABLE IF NOT EXISTS task_dependencies' in c4
    assert 'CREATE TABLE IF NOT EXISTS sub_tasks' in c4
test("Migration files: 003_notion_tables + 004_dependencies_subtasks", t12)

# Summary
print(f"\n{'='*40}")
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL PHASE 2 & 2.5 TESTS PASSED")
else:
    print("SOME TESTS FAILED")
    sys.exit(1)
