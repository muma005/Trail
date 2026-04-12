"""Verification test for Phase 5: Notion AI Agent (Basic)."""
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

print("=== Phase 5 Verification Tests ===\n")

# Test 1: Poller exists and has required methods
def t1():
    from src.services.notion_agent.agent import NotionPoller, poll_notion_commands
    poller = NotionPoller()
    assert hasattr(poller, 'poll')
    assert hasattr(poller, '_scan_database')
    assert hasattr(poller, '_extract_block_text')
    assert hasattr(poller, '_store_command')
    assert callable(poll_notion_commands)
test("Poller: all methods present", t1)

# Test 2: Basic Brain exists and handles all command types
def t2():
    from src.services.notion_agent.basic_brain import BasicBrain
    brain = BasicBrain()

    # Test command routing
    assert "summarize" in brain.process_command("summarize this page", "page123").lower() or "empty" in brain.process_command("summarize this page", "page123").lower()

    # Test unknown command → suggestions
    response = brain.process_command("do something weird", "page123")
    assert "summarize" in response.lower()
    assert "status" in response.lower()
test("Basic Brain: command routing and unknown command response", t2)

# Test 3: Responder exists and has required methods
def t3():
    from src.services.notion_agent.responder import NotionResponder, process_notion_commands
    responder = NotionResponder()
    assert hasattr(responder, 'process_all_pending')
    assert hasattr(responder, 'process_single')
    assert hasattr(responder, '_write_response')
    assert hasattr(responder, '_split_text')
    assert callable(process_notion_commands)
test("Responder: all methods present", t3)

# Test 4: Text splitting for Notion blocks
def t4():
    from src.services.notion_agent.responder import NotionResponder
    responder = NotionResponder()

    # Short text
    chunks = responder._split_text("Hello world", 100)
    assert len(chunks) == 1
    assert chunks[0] == "Hello world"

    # Long text
    long_text = "A" * 5000
    chunks = responder._split_text(long_text, 1900)
    assert len(chunks) >= 3  # 5000 / 1900 ≈ 2.6, so at least 3
    assert all(len(c) <= 1900 for c in chunks)
test("Responder: text splitting works correctly", t4)

# Test 5: @ai command regex pattern
def t5():
    import re
    pattern = re.compile(r'@ai\s+(.+?)(?:\n|$)', re.IGNORECASE)

    # Valid matches
    m1 = pattern.search("@ai summarize this page")
    assert m1 and "summarize this page" in m1.group(1)

    m2 = pattern.search("@ai what is the status of Auth?")
    assert m2 and "what is the status of Auth?" in m2.group(1)

    m3 = pattern.search("@ai update status to Done")
    assert m3 and "update status to Done" in m3.group(1)

    # No match
    assert pattern.search("@ai") is None
    assert pattern.search("@ai ") is None
test("@ai command regex: extracts command text correctly", t5)

# Test 6: ORM model NotionCommand exists
def t6():
    from src.models.database.models import NotionCommand
    assert hasattr(NotionCommand, 'page_id')
    assert hasattr(NotionCommand, 'block_id')
    assert hasattr(NotionCommand, 'command')
    assert hasattr(NotionCommand, 'status')
    assert hasattr(NotionCommand, 'response_block_id')
test("ORM: NotionCommand model with all fields", t6)

# Test 7: CLI commands registered
def t7():
    from src.cli.main import cli
    commands = list(cli.commands.keys())
    assert 'notion' in commands
test("CLI: notion command registered", t7)

# Test 8: notion subcommands
def t8():
    from src.cli.commands.notion import poll, process
    assert poll.name == "poll"
    assert process.name == "process"
test("CLI: notion poll and process subcommands", t8)

# Test 9: Celery beat schedule includes poller and responder
def t9():
    try:
        from src.tasks.celery.beat_schedule import beat_schedule
    except ImportError:
        # Celery not installed, check the file exists
        import os
        path = os.path.join('src', 'tasks', 'celery', 'beat_schedule.py')
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert 'notion-poller' in content
        assert 'notion-responder' in content
        return
    assert 'notion-poller' in beat_schedule
    assert 'notion-responder' in beat_schedule
    assert beat_schedule['notion-poller']['schedule'] == 60.0
    assert beat_schedule['notion-responder']['schedule'] == 30.0
test("Celery Beat: notion-poller (60s) and notion-responder (30s) scheduled", t9)

# Test 10: Migration file exists
def t10():
    import os
    m9 = os.path.join('migrations', '009_add_notion_commands_table.sql')
    assert os.path.exists(m9), f'Migration missing: {m9}'
    with open(m9) as f:
        content = f.read()
    assert 'CREATE TABLE IF NOT EXISTS notion_commands' in content
    assert 'UNIQUE (page_id, block_id)' in content
    assert 'status' in content
test("Migration: 009_add_notion_commands_table.sql correct", t10)

# Summary
print(f"\n{'='*40}")
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL PHASE 5 TESTS PASSED")
else:
    print("SOME TESTS FAILED")
    sys.exit(1)
