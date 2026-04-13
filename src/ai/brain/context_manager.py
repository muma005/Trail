"""
Conversation manager for the AI Brain.
Phase 9: Manages sessions, message history, and semantic memory retrieval.
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.models.database.base import SessionLocal
from src.models.database.models import Conversation

logger = logging.getLogger(__name__)


class ConversationManager:
    """
    Manages conversation sessions, message storage, and semantic memory retrieval.
    """

    def start_session(self, user_id: Optional[str] = None) -> str:
        """
        Create a new conversation session.

        Args:
            user_id: User UUID (generates one if not provided)

        Returns:
            session_id UUID string
        """
        session_id = str(uuid.uuid4())
        if user_id is None:
            user_id = str(uuid.uuid4())

        # Store system message to initialize session
        db = SessionLocal()
        try:
            system_msg = Conversation(
                user_id=user_id,
                session_id=session_id,
                role="system",
                content="You are Trail, an AI-enabled progress tracker and work planner. "
                        "You help users track progress across GitHub and Notion, plan their work, "
                        "and answer questions about their projects.",
            )
            db.add(system_msg)
            db.commit()
            logger.info(f"Started new conversation session: {session_id[:8]}")
            return session_id
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to start session: {e}")
            raise
        finally:
            db.close()

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tool_call_id: Optional[str] = None,
        user_id: Optional[str] = None,
        embedding: Optional[List[float]] = None,
    ) -> str:
        """
        Add a message to the conversation.

        Args:
            session_id: Session UUID
            role: 'user', 'assistant', or 'system'
            content: Message text
            tool_calls: List of tool call dicts (for assistant messages)
            tool_call_id: Matching ID for tool responses
            user_id: User UUID (retrieved from existing messages if not provided)
            embedding: Vector embedding for semantic search

        Returns:
            Message ID
        """
        db = SessionLocal()
        try:
            # Get user_id from existing message if not provided
            if user_id is None:
                first_msg = (
                    db.query(Conversation)
                    .filter(Conversation.session_id == session_id)
                    .order_by(Conversation.timestamp)
                    .first()
                )
                if first_msg:
                    user_id = str(first_msg.user_id)
                else:
                    user_id = str(uuid.uuid4())

            msg = Conversation(
                user_id=user_id,
                session_id=session_id,
                role=role,
                content=content,
                tool_calls=json.dumps(tool_calls) if tool_calls else None,
                tool_call_id=tool_call_id,
                timestamp=datetime.utcnow(),
                embedding_text=json.dumps(embedding) if embedding else None,
            )
            db.add(msg)
            db.commit()
            db.refresh(msg)
            return str(msg.id)
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to add message: {e}")
            raise
        finally:
            db.close()

    def get_conversation_history(
        self, session_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get the last N messages from a conversation session.

        Args:
            session_id: Session UUID
            limit: Number of messages to retrieve

        Returns:
            List of message dicts with role, content, tool_calls, etc.
        """
        db = SessionLocal()
        try:
            messages = (
                db.query(Conversation)
                .filter(Conversation.session_id == session_id)
                .order_by(Conversation.timestamp.desc())
                .limit(limit)
                .all()
            )

            # Reverse to get chronological order
            messages = list(reversed(messages))

            result = []
            for msg in messages:
                msg_dict = {
                    "role": msg.role,
                    "content": msg.content,
                    "tool_calls": json.loads(msg.tool_calls) if msg.tool_calls else None,
                    "tool_call_id": msg.tool_call_id,
                    "timestamp": str(msg.timestamp),
                }
                result.append(msg_dict)

            return result
        except Exception as e:
            logger.error(f"Failed to get conversation history: {e}")
            return []
        finally:
            db.close()

    def get_similar_messages(
        self, query: str, session_id: Optional[str] = None, limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find semantically similar past messages using vector similarity.

        For MVP without pgvector, we use keyword-based matching as fallback.
        When pgvector is available, this would use cosine similarity on embeddings.

        Args:
            query: Search query text
            session_id: Optional session to limit search to
            limit: Number of results

        Returns:
            List of similar message dicts
        """
        db = SessionLocal()
        try:
            # MVP fallback: keyword-based similarity
            # Split query into keywords and find messages containing them
            query_words = set(query.lower().split())
            query_words = {w for w in query_words if len(w) > 3}  # Skip short words

            # Get recent messages to search through
            query_db = db.query(Conversation).filter(
                Conversation.role.in_(["user", "assistant"])
            )
            if session_id:
                query_db = query_db.filter(Conversation.session_id == session_id)

            messages = query_db.order_by(Conversation.timestamp.desc()).limit(200).all()

            # Score each message by keyword overlap
            scored = []
            for msg in messages:
                content_lower = msg.content.lower()
                content_words = set(content_lower.split())
                overlap = query_words & content_words
                if overlap:
                    score = len(overlap) / max(1, len(query_words))
                    scored.append((score, msg))

            # Sort by score descending
            scored.sort(key=lambda x: x[0], reverse=True)

            result = []
            for score, msg in scored[:limit]:
                result.append({
                    "role": msg.role,
                    "content": msg.content,
                    "similarity": round(score, 3),
                    "timestamp": str(msg.timestamp),
                })

            return result

        except Exception as e:
            logger.error(f"Failed to get similar messages: {e}")
            return []
        finally:
            db.close()

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get basic info about a conversation session."""
        db = SessionLocal()
        try:
            first_msg = (
                db.query(Conversation)
                .filter(Conversation.session_id == session_id)
                .order_by(Conversation.timestamp)
                .first()
            )
            last_msg = (
                db.query(Conversation)
                .filter(Conversation.session_id == session_id)
                .order_by(Conversation.timestamp.desc())
                .first()
            )

            if not first_msg:
                return None

            count = (
                db.query(Conversation)
                .filter(Conversation.session_id == session_id)
                .count()
            )

            return {
                "session_id": session_id,
                "user_id": str(first_msg.user_id),
                "started": str(first_msg.timestamp),
                "last_activity": str(last_msg.timestamp) if last_msg else None,
                "message_count": count,
            }
        except Exception as e:
            logger.error(f"Failed to get session info: {e}")
            return None
        finally:
            db.close()

    def reset_session(self, session_id: str) -> int:
        """Delete all messages in a session."""
        db = SessionLocal()
        try:
            count = (
                db.query(Conversation)
                .filter(Conversation.session_id == session_id)
                .delete()
            )
            db.commit()
            logger.info(f"Reset session {session_id[:8]}: deleted {count} messages")
            return count
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to reset session: {e}")
            return 0
        finally:
            db.close()


def get_conversation_manager() -> ConversationManager:
    """Factory function for conversation manager."""
    return ConversationManager()
