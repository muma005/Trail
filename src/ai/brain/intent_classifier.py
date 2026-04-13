"""
Intent classifier for the AI Brain.
Phase 9: Classifies user queries into intents (query, action, clarification).
"""
import re
from typing import Dict, Optional


class IntentClassifier:
    """
    Simple keyword-based intent classifier.
    Can be replaced with ML model later.
    """

    INTENT_QUERY = "query"
    INTENT_ACTION = "action"
    INTENT_CLARIFICATION = "clarification"
    INTENT_GREETING = "greeting"
    INTENT_HELP = "help"

    ACTION_KEYWORDS = {"update", "set", "change", "create", "add", "delete", "remove", "archive", "reschedule"}
    QUERY_KEYWORDS = {"what", "how", "when", "where", "who", "why", "show", "list", "get", "status", "progress", "plan"}
    GREETING_KEYWORDS = {"hello", "hi", "hey", "good morning", "good afternoon"}
    HELP_KEYWORDS = {"help", "help me", "what can you do", "commands", "usage"}

    def classify(self, text: str) -> Dict[str, Optional[str]]:
        """
        Classify text into intent and extract key entities.

        Args:
            text: User's query text

        Returns:
            Dict with 'intent' and optional 'project_key', 'task_id', etc.
        """
        text_lower = text.lower().strip()

        # Check greetings
        if any(kw in text_lower for kw in self.GREETING_KEYWORDS):
            return {"intent": self.INTENT_GREETING}

        # Check help
        if any(kw in text_lower for kw in self.HELP_KEYWORDS):
            return {"intent": self.INTENT_HELP}

        # Check actions
        if any(kw in text_lower for kw in self.ACTION_KEYWORDS):
            intent = self.INTENT_ACTION
        elif any(kw in text_lower for kw in self.QUERY_KEYWORDS):
            intent = self.INTENT_QUERY
        else:
            intent = self.INTENT_QUERY  # Default

        # Extract entities
        entities = {"intent": intent}

        # Extract project key (e.g., AUTH-01, PROJ-123)
        project_match = re.search(r'([A-Z]+-\d+)', text)
        if project_match:
            entities["project_key"] = project_match.group(1)

        # Extract task-related keywords
        if "status" in text_lower:
            entities["entity_type"] = "task_status"
        elif "plan" in text_lower or "today" in text_lower:
            entities["entity_type"] = "plan"
        elif "progress" in text_lower:
            entities["entity_type"] = "progress"
        elif "untracked" in text_lower:
            entities["entity_type"] = "untracked"

        return entities


def get_intent_classifier() -> IntentClassifier:
    """Factory function for intent classifier."""
    return IntentClassifier()
