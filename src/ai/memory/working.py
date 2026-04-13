"""
Working memory layer.
Phase 9: Holds current session context (active project, recent decisions).
"""
from src.ai.memory.episodic import WorkingMemory

# Re-export for convenience
__all__ = ["WorkingMemory"]
