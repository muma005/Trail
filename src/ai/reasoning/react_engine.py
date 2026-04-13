"""
ReAct loop for the AI Brain.
Phase 9: LLM decides which tool to call, executes it, observes result, iterates.
Includes deterministic ID guard for project-based tool calls.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

from src.ai.brain.context_manager import get_conversation_manager
from src.ai.tools.base_tool import create_default_tool_registry, ToolRegistry

logger = logging.getLogger(__name__)

# System prompt for the ReAct loop
SYSTEM_PROMPT = """You are Trail, an AI-enabled progress tracker and work planner.
You help users track progress across GitHub and Notion, plan their work, and answer questions.

You have access to the following tools. Use them when you need data or need to perform an action.

AVAILABLE TOOLS:
{tools}

RULES:
1. If you need to call a tool, output ONLY a JSON object like:
   {{"tool": "tool_name", "arguments": {{"arg1": "value1"}}}}
2. After receiving a tool result, continue reasoning and either call another tool or give your final answer.
3. If the user asks about a project but doesn't specify which one, ask for clarification.
   Say: "Which project do you mean? You have: [list of project keys]."
4. If a tool call fails, explain the error and suggest alternatives.
5. Maximum 5 tool call iterations. After that, give your best answer.
6. When giving your final answer, output ONLY the text response (no JSON).
7. Always be concise and helpful.
"""

MAX_ITERATIONS = 5


class ReActEngine:
    """
    Implements the ReAct loop: Reason → Act (call tool) → Observe → repeat.
    """

    def __init__(self, tool_registry: Optional[ToolRegistry] = None):
        self.tools = tool_registry or create_default_tool_registry()
        self.cm = get_conversation_manager()

    def process_query(
        self,
        query: str,
        session_id: str,
        user_id: Optional[str] = None,
    ) -> str:
        """
        Process a user query through the ReAct loop.

        Args:
            query: User's question or command
            session_id: Conversation session ID
            user_id: User UUID

        Returns:
            Assistant's response text
        """
        # Add user message to history
        self.cm.add_message(session_id, "user", query, user_id=user_id)

        # Get conversation history
        history = self.cm.get_conversation_history(session_id, limit=10)

        # Get similar past messages for context
        similar = self.cm.get_similar_messages(query, session_id=session_id, limit=2)

        # Build messages for LLM
        messages = self._build_messages(query, history, similar)

        # Run ReAct loop
        response = self._react_loop(messages, session_id, user_id)

        # Store assistant response
        self.cm.add_message(session_id, "assistant", response, user_id=user_id)

        return response

    def _react_loop(
        self,
        messages: List[Dict[str, Any]],
        session_id: str,
        user_id: Optional[str],
    ) -> str:
        """
        Run the ReAct loop: call LLM, parse tool calls, execute, observe, repeat.

        Args:
            messages: List of messages for LLM
            session_id: Session ID
            user_id: User ID

        Returns:
            Final response text
        """
        # For MVP without actual LLM call, we'll use rule-based responses
        # In production, this would call OpenRouter API
        last_message = messages[-1]["content"] if messages else ""

        # Check if this is a tool call that needs execution
        tool_result = self._try_parse_tool_call(last_message)
        if tool_result:
            tool_name = tool_result["tool"]
            args = tool_result.get("arguments", {})

            # Check for project_key requirement
            if "project_key" in args and not args["project_key"]:
                return self._ask_for_project()

            # Execute tool
            result = self.tools.execute_tool(tool_name, **args)
            if result.get("success"):
                return str(result.get("result", "Done."))
            else:
                return f"❌ Tool failed: {result.get('error', 'Unknown error')}"

        # MVP: Rule-based responses for common queries
        return self._generate_response(last_message, session_id)

    def _build_messages(
        self,
        query: str,
        history: List[Dict[str, Any]],
        similar: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Build the message list for the LLM."""
        tools_str = json.dumps(self.tools.get_all_definitions(), indent=2)
        system_content = SYSTEM_PROMPT.format(tools=tools_str)

        messages = [{"role": "system", "content": system_content}]

        # Add similar past messages as context
        if similar:
            context_parts = []
            for msg in similar:
                context_parts.append(
                    f"Previous conversation ({msg['similarity']:.0%} match): "
                    f"[{msg['role']}] {msg['content']}"
                )
            messages.append({
                "role": "system",
                "content": "From previous conversations:\n" + "\n".join(context_parts),
            })

        # Add conversation history
        for msg in history:
            if msg["role"] != "system":
                messages.append({"role": msg["role"], "content": msg["content"]})

        # Add current query
        messages.append({"role": "user", "content": query})

        return messages

    def _try_parse_tool_call(self, text: str) -> Optional[Dict[str, Any]]:
        """Try to parse a JSON tool call from text."""
        # Look for JSON object
        match = re.search(r'\{[^{}]*"tool"[^{}]*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return None

    def _ask_for_project(self) -> str:
        """Ask user to specify a project."""
        from src.models.database.base import SessionLocal
        from src.models.database.models import Project

        db = SessionLocal()
        try:
            projects = db.query(Project).filter(Project.status == "active").all()
            if projects:
                keys = ", ".join(f"{p.project_key}" for p in projects)
                return f"Which project do you mean? You have: {keys}."
            return "You don't have any active projects. Add one first with `trail project add`."
        finally:
            db.close()

    def _generate_response(self, query: str, session_id: str) -> str:
        """Generate a rule-based response for MVP."""
        query_lower = query.lower()

        # Greeting
        if any(g in query_lower for g in ["hello", "hi", "hey"]):
            return "Hello! I'm Trail, your AI progress tracker. Ask me about your projects, plans, or progress!"

        # Help
        if "help" in query_lower:
            return (
                "I can help with:\n"
                "• Project status: 'what's the status of AUTH-01?'\n"
                "• Today's plan: 'what's planned for today?'\n"
                "• Progress: 'how is Project A going?'\n"
                "• Untracked work: 'any untracked sessions?'\n"
                "• Focus peaks: 'when am I most productive?'"
            )

        # Status query
        if "status" in query_lower or "progress" in query_lower:
            return "To check project status, specify the project key. Example: 'status of AUTH-01'"

        # Plan query
        if "plan" in query_lower or "today" in query_lower:
            return "Run `trail plan today` to see today's work plan, or ask me 'what's planned today?'"

        # Default
        return (
            f"I understand you're asking about: '{query}'.\n"
            "For now, I'm in MVP mode with rule-based responses. "
            "Connect OpenRouter API for full AI capabilities."
        )


def get_react_engine() -> ReActEngine:
    """Factory function for ReAct engine."""
    return ReActEngine()
