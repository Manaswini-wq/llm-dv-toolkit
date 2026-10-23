"""Embedding-based failure classifier using LLM embeddings."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any
import math


class FailureCategory(Enum):
    """Failure classification categories."""
    RTL_BUG = "rtl_bug"
    TB_BUG = "testbench_bug"
    ENV_ISSUE = "environment_issue"
    SEED_SENSITIVE = "seed_sensitive"
    INFRA = "infrastructure"
    UNKNOWN = "unknown"


@dataclass
class ClassifiedFailure:
    """A classified failure with confidence and similar past failures."""
    error_message: str
    category: FailureCategory
    confidence: float
    similar_failures: list[dict[str, Any]] = field(default_factory=list)
    resolution: str = ""


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def simple_embedding(text: str, dim: int = 64) -> list[float]:
    """Simple hash-based embedding for when API is unavailable.

    This is a fallback -- in production, use OpenAI/Anthropic embeddings.
    """
    import hashlib
    embedding = [0.0] * dim
    words = text.lower().split()
    for i, word in enumerate(words):
        h = int(hashlib.md5(word.encode()).hexdigest(), 16)
        for j in range(dim):
            embedding[j] += ((h >> j) & 1) * 2 - 1
    # Normalize
    norm = math.sqrt(sum(x * x for x in embedding)) or 1.0
    return [x / norm for x in embedding]


class FailureClassifier:
    """Classify failures using embeddings and knowledge base."""

    SIMILARITY_THRESHOLD = 0.75

    def __init__(self, kb_path: Path | None = None) -> None:
        self.kb_path = kb_path or Path("failure_kb.db")
        self._conn = sqlite3.connect(str(self.kb_path))
        self._init_db()

    def _init_db(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS known_failures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_message TEXT NOT NULL,
                category TEXT NOT NULL,
                resolution TEXT DEFAULT '',
                embedding TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self._conn.commit()

    def classify(self, error_message: str) -> ClassifiedFailure:
        """Classify a failure by comparing against known failures."""
        emb = simple_embedding(error_message)

        # Find similar known failures
        rows = self._conn.execute(
            "SELECT error_message, category, resolution, embedding FROM known_failures"
        ).fetchall()

        similarities: list[tuple[float, dict[str, Any]]] = []
        for msg, cat, res, emb_json in rows:
            known_emb = json.loads(emb_json)
            sim = cosine_similarity(emb, known_emb)
            if sim >= self.SIMILARITY_THRESHOLD:
                similarities.append((sim, {
                    "message": msg, "category": cat, "resolution": res, "similarity": round(sim, 3),
                }))

        similarities.sort(key=lambda x: x[0], reverse=True)

        if similarities:
            best = similarities[0]
            return ClassifiedFailure(
                error_message=error_message,
                category=FailureCategory(best[1]["category"]),
                confidence=best[0],
                similar_failures=[s[1] for s in similarities[:5]],
                resolution=best[1]["resolution"],
            )

        # Rule-based fallback
        category = self._rule_classify(error_message)
        return ClassifiedFailure(
            error_message=error_message,
            category=category,
            confidence=0.4,
        )

    def add_known_failure(
        self, error_message: str, category: FailureCategory, resolution: str = "",
    ) -> None:
        """Add a classified failure to the knowledge base."""
        emb = simple_embedding(error_message)
        self._conn.execute(
            "INSERT INTO known_failures (error_message, category, resolution, embedding) VALUES (?,?,?,?)",
            (error_message, category.value, resolution, json.dumps(emb)),
        )
        self._conn.commit()

    def _rule_classify(self, msg: str) -> FailureCategory:
        msg_lower = msg.lower()
        if "mismatch" in msg_lower or "expected" in msg_lower:
            return FailureCategory.RTL_BUG
        if "timeout" in msg_lower or "hung" in msg_lower:
            return FailureCategory.ENV_ISSUE
        if "license" in msg_lower or "file not found" in msg_lower:
            return FailureCategory.INFRA
        if "segfault" in msg_lower or "core dump" in msg_lower:
            return FailureCategory.INFRA
        return FailureCategory.UNKNOWN

    def close(self) -> None:
        self._conn.close()
