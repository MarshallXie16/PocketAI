"""Long-term memory store.

Replaces the Pinecone-backed ``src/components/memory.py``. Memories live in
the app database (``MemoryEntry``) with embeddings as float32 blobs; ranking
is in-process cosine similarity over a (user, ai) pair's rows — small-N by
design (a companion's per-relationship memory is hundreds of rows, not
millions). Swap the ranking for pgvector when a managed Postgres exists.

Phase 4a layers episodic scoring (recency/reinforcement/importance) on top;
Phase 3 ships pure similarity so behavior matches the old Pinecone top-k.
"""

import datetime
import logging

import numpy as np

from src.models.memory_entry import MemoryEntry
from src.utils.extensions import db

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = 'text-embedding-3-small'
EMBEDDING_DIMS = 1536


def _embed(text: str) -> bytes:
    from src.providers.registry import get_openai_client

    response = get_openai_client().embeddings.create(input=text, model=EMBEDDING_MODEL)
    return np.asarray(response.data[0].embedding, dtype=np.float32).tobytes()


def save_memory(user_id: int, ai_id: int, content: str, *, emotional_tone=None,
                key_insight=None, importance=0.5, entity_tags=None) -> MemoryEntry:
    entry = MemoryEntry(
        user_id=user_id,
        ai_id=ai_id,
        content=content,
        embedding=_embed(content),
        emotional_tone=emotional_tone,
        key_insight=key_insight,
        importance=importance,
        entity_tags=entity_tags or [],
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def search_memory(user_id: int, ai_id: int, query: str, top_k: int = 3) -> list[str]:
    """Return the top_k most similar memory contents for this (user, ai) pair."""
    rows = MemoryEntry.query.filter_by(user_id=user_id, ai_id=ai_id).all()
    if not rows:
        return []

    query_vec = np.frombuffer(_embed(query), dtype=np.float32)
    matrix = np.vstack([np.frombuffer(r.embedding, dtype=np.float32) for r in rows])
    # cosine similarity; embeddings from OpenAI are unit-length but normalize defensively
    norms = np.linalg.norm(matrix, axis=1) * (np.linalg.norm(query_vec) or 1.0)
    scores = matrix @ query_vec / np.where(norms == 0, 1.0, norms)

    ranked = sorted(zip(scores, rows), key=lambda pair: -pair[0])[:top_k]

    now = datetime.datetime.now(datetime.UTC)
    for _, row in ranked:
        row.last_accessed = now
        row.access_count += 1
    db.session.commit()

    return [row.content for _, row in ranked]
