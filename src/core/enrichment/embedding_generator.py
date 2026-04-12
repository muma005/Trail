"""
Embedding helper for commit-task similarity matching.
Phase 2: Uses sentence-transformers for cosine similarity between commit messages and task titles.
"""
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# Similarity threshold for suggestions
SIMILARITY_THRESHOLD = 0.7


class EmbeddingHelper:
    """
    Lightweight embedding generator and comparator.
    Uses sentence-transformers if available, falls back to simple text matching if not.
    """

    def __init__(self):
        self._model = None
        self._available = False

    @property
    def model(self):
        """Lazy-load the embedding model. Returns None if unavailable."""
        if self._model is None and not self._available:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer("all-MiniLM-L6-v2")
                self._available = True
                logger.info("Loaded sentence-transformers model: all-MiniLM-L6-v2")
            except ImportError:
                logger.warning(
                    "sentence-transformers not installed. "
                    "Embedding-based linking disabled. "
                    "Install with: pip install sentence-transformers"
                )
                self._available = False
            except Exception as e:
                logger.warning(f"Failed to load embedding model: {e}")
                self._available = False
        return self._model

    def is_available(self) -> bool:
        """Check if embedding model is loaded."""
        return self._available and self.model is not None

    def encode(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.
        Returns list of embedding vectors.
        """
        if not self.is_available():
            return []
        try:
            embeddings = self.model.encode(texts)
            return embeddings.tolist()
        except Exception as e:
            logger.warning(f"Failed to encode texts: {e}")
            return []

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Compute cosine similarity between two vectors.
        Returns value between -1 and 1.
        """
        import numpy as np

        v1 = np.array(vec1)
        v2 = np.array(vec2)

        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(np.dot(v1, v2) / (norm1 * norm2))

    def find_suggestions(
        self,
        commit_messages: List[Tuple[str, str]],  # (commit_sha, message)
        tasks: List[Tuple[str, str]],             # (task_id, title)
    ) -> List[Dict[str, any]]:
        """
        Find potential commit-task links via embedding similarity.

        Args:
            commit_messages: List of (commit_sha, message) tuples
            tasks: List of (task_id, title) tuples

        Returns:
            List of suggestions: {commit_sha, task_id, confidence}
            Only returns suggestions above SIMILARITY_THRESHOLD.
        """
        if not self.is_available():
            logger.info("Embedding model unavailable, skipping similarity matching")
            return []

        if not commit_messages or not tasks:
            return []

        # Generate embeddings
        commit_texts = [msg for _, msg in commit_messages]
        task_texts = [title for _, title in tasks]

        commit_embeddings = self.encode(commit_texts)
        task_embeddings = self.encode(task_texts)

        if not commit_embeddings or not task_embeddings:
            return []

        import numpy as np

        suggestions = []

        for i, (commit_sha, _) in enumerate(commit_messages):
            for j, (task_id, _) in enumerate(tasks):
                sim = self.cosine_similarity(commit_embeddings[i], task_embeddings[j])

                if sim >= SIMILARITY_THRESHOLD:
                    suggestions.append({
                        "commit_sha": commit_sha,
                        "task_id": task_id,
                        "confidence": round(sim, 2),
                    })

        # Sort by confidence descending
        suggestions.sort(key=lambda x: x["confidence"], reverse=True)
        logger.info(f"Generated {len(suggestions)} embedding-based suggestions")
        return suggestions


# Singleton instance
embedder = EmbeddingHelper()
