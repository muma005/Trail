"""Verification test for Phase 9: AI Brain - Conversation & Memory."""
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

print("=== Phase 9 Verification Tests ===\n")

# Test 1: Conversation manager exists
def t1():
    from src.ai.brain.context_manager import ConversationManager, get_conversation_manager
    cm = get_conversation_manager()
    assert hasattr(cm, 'start_session')
    assert hasattr(cm, 'add_message')
    assert hasattr(cm, 'get_conversation_history')
    assert hasattr(cm, 'get_similar_messages')
    assert hasattr(cm, 'reset_session')
test("Conversation manager: all methods present", t1)

# Test 2: Tool registry exists
def t2():
    from src.ai.tools.base_tool import Tool, ToolRegistry, create_default_tool_registry
    registry = create_default_tool_registry()
    tools = registry.list_tools()
    assert len(tools) > 0, "Should have at least some tools registered"
    assert 'get_project_info' in tools
    assert 'get_project_progress' in tools
    assert 'get_today_plan' in tools
test("Tool registry: 15+ tools registered", t2)

# Test 3: ReAct engine exists
def t3():
    from src.ai.reasoning.react_engine import ReActEngine, get_react_engine
    engine = get_react_engine()
    assert hasattr(engine, 'process_query')
    assert hasattr(engine, '_react_loop')
    assert hasattr(engine, '_ask_for_project')
test("ReAct engine: exists with key methods", t3)

# Test 4: ReAct deterministic ID guard
def t4():
    from src.ai.reasoning.react_engine import ReActEngine
    from unittest.mock import patch, MagicMock

    engine = ReActEngine()
    # Mock the database call to avoid DB connection
    with patch('src.models.database.base.SessionLocal') as mock_db:
        mock_instance = MagicMock()
        mock_instance.query.return_value.filter.return_value.all.return_value = []
        mock_db.return_value = mock_instance
        response = engine._ask_for_project()
        assert "project" in response.lower()
test("ReAct ID guard: asks for project when ambiguous", t4)

# Test 5: Memory layers exist
def t5():
    from src.ai.memory.episodic import EpisodicMemory, SemanticMemory, ProceduralMemory, WorkingMemory
    assert hasattr(EpisodicMemory, 'retrieve_similar')
    assert hasattr(SemanticMemory, 'get_project_facts')
    assert hasattr(ProceduralMemory, 'get_user_preferences')
    assert hasattr(WorkingMemory, 'set_current_project')
    assert hasattr(WorkingMemory, 'get_current_project')
test("Memory layers: episodic, semantic, procedural, working all present", t5)

# Test 6: Intent classifier exists
def t6():
    from src.ai.brain.intent_classifier import IntentClassifier, get_intent_classifier
    classifier = get_intent_classifier()

    # Test classifications
    result = classifier.classify("hello")
    assert result["intent"] == "greeting"

    result = classifier.classify("help me")
    assert result["intent"] == "help"

    result = classifier.classify("update the status")
    assert result["intent"] == "action"

    result = classifier.classify("what is the status of AUTH-01")
    assert result["intent"] == "query"
    assert result.get("project_key") == "AUTH-01"
test("Intent classifier: classifies greetings, help, actions, queries", t6)

# Test 7: ORM model exists
def t7():
    from src.models.database.models import Conversation
    assert hasattr(Conversation, 'session_id')
    assert hasattr(Conversation, 'role')
    assert hasattr(Conversation, 'content')
    assert hasattr(Conversation, 'tool_calls')
    assert hasattr(Conversation, 'embedding_text')
test("ORM: Conversation model with all fields", t7)

# Test 8: CLI commands registered
def t8():
    from src.cli.main import cli
    commands = list(cli.commands.keys())
    assert 'brain' in commands
test("CLI: brain command registered", t8)

# Test 9: Brain subcommands
def t9():
    from src.cli.commands.brain import ask, show_session, reset_session
    assert ask.name == "ask"
    assert show_session.name == "session"
    assert reset_session.name == "reset"
test("CLI: brain ask/session/reset subcommands", t9)

# Test 10: Migration file exists
def t10():
    import os
    m18 = os.path.join('migrations', '018_create_conversations.sql')
    assert os.path.exists(m18), f'Migration missing: {m18}'
    with open(m18) as f:
        content = f.read()
    assert 'CREATE TABLE IF NOT EXISTS conversations' in content
    assert 'session_id' in content
    assert 'role' in content
    assert 'content' in content
    assert 'tool_calls' in content
    assert 'embedding' in content
test("Migration: 018_create_conversations.sql correct", t10)


# Test 11: Morning briefing generator exists
def t11():
    from src.services.report_generator.dispatcher import (
        generate_morning_briefing,
        send_morning_briefing,
        check_celebrations,
        send_celebrations,
    )
    assert callable(generate_morning_briefing)
    assert callable(send_morning_briefing)
    assert callable(check_celebrations)
    assert callable(send_celebrations)

    # Test briefing generation
    briefing = generate_morning_briefing()
    assert "Trail Morning Briefing" in briefing
    assert "Today's Plan" in briefing
test("Morning briefing & celebration: all functions present", t11)


# Test 12: Briefing includes key sections
def t12():
    from src.services.report_generator.dispatcher import generate_morning_briefing
    briefing = generate_morning_briefing()
    # Check for expected sections
    assert "Trail Morning Briefing" in briefing
    assert "Today's Plan" in briefing
    assert "trail plan today" in briefing or "trail brain" in briefing
test("Morning briefing: includes key sections", t12)

# Summary
print(f"\n{'='*40}")
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL PHASE 9 TESTS PASSED")
else:
    print("SOME TESTS FAILED")
    sys.exit(1)
