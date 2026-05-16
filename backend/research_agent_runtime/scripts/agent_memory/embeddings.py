from __future__ import annotations

import json
import math
from typing import Any

from .models import stable_id, tokenize, now


VECTOR_SIZE = 128


def create_embedding(text: str) -> list[float]:
    """Local hashed bag-of-words embedding used when no external provider is configured."""
    import hashlib

    vector = [0.0] * VECTOR_SIZE
    for token in tokenize(text):
        idx = int(hashlib.sha1(token.encode("utf-8")).hexdigest(), 16) % VECTOR_SIZE
        vector[idx] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def store_embedding(conn: Any, memory_id: str, text: str, provider: str = "local_hash") -> str:
    embedding_id = stable_id(provider, memory_id, text[:200])
    conn.execute(
        """
        INSERT OR REPLACE INTO memory_embeddings(id, memory_id, provider, vector_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (embedding_id, memory_id, provider, json.dumps(create_embedding(text)), now()),
    )
    return embedding_id


def search_similar_embeddings(query_embedding: list[float], rows: list[dict[str, Any]], max_results: int = 20) -> list[dict[str, Any]]:
    scored = []
    for row in rows:
        vector = row.get("embedding_vector")
        if not isinstance(vector, list):
            continue
        item = dict(row)
        item["semantic_score"] = cosine(query_embedding, vector)
        scored.append(item)
    scored.sort(key=lambda item: item["semantic_score"], reverse=True)
    return scored[:max_results]
