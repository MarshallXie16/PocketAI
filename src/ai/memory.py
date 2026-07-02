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

from src.extensions import db
from src.models.memory_entry import MemoryEntry

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


def consolidate_and_save(user_id: int, ai_id: int, queue_lines: list[str],
                         ai_name: str, username: str) -> None:
    """Summarize a batch of exchanges and persist it if it matters.

    Runs on the background executor after a chat turn returns — the LLM
    gate ("is this worth remembering?") + embedding + write are all off the
    hot path. Ported from the legacy utilities.summarize prompt.
    """
    import datetime as _dt

    from config import UTILITY_MODEL
    from src.providers.registry import get_provider

    prompt = f'''You are {ai_name} having a chat with {username}. Analyze this conversation snippet and determine if there's important information to remember.
Examples of important information:
1. New details about people, places, events, or things
2. New information about {username}'s preferences, interests, or experiences
3. Changes in {username}'s life or circumstances
4. Emotional states or reactions that provide context for future conversations

If important information is found:
- summarize it in 50 words or less from the perspective of {ai_name}

If no important information is found, respond with only the word 'false'.'''

    result = get_provider(UTILITY_MODEL).generate(
        model=UTILITY_MODEL,
        system=prompt,
        messages=[{'role': 'user', 'content': f'Conversation snippet: {queue_lines}. Summary (if important): '}],
        max_tokens=200,
    )
    summary = (result.text or '').strip()
    if summary and summary.lower() != 'false':
        stamped = _dt.datetime.now(_dt.UTC).strftime('%Y-%m-%d %H:%M:%S ') + summary
        save_memory(user_id, ai_id, stamped)
        logger.info('Memory saved (user=%s ai=%s)', user_id, ai_id)
    else:
        logger.info('Memory gate: nothing worth saving (user=%s ai=%s)', user_id, ai_id)

    # Success (or an intentional gate-drop): remove exactly the consumed
    # lines from the live queue. On exception we never reach here, the queue
    # stays intact, and the next full turn retries — no silent memory loss.
    _consume_queue_lines(user_id, ai_id, queue_lines)


def _consume_queue_lines(user_id: int, ai_id: int, consumed: list[str]) -> None:
    from src.models.conversation_state import ConversationState

    state = ConversationState.query.filter_by(user_id=user_id, ai_id=ai_id).first()
    if state is None:
        return
    remaining = [line for line in (state.memory_queue or []) if line not in consumed]
    state.memory_queue = remaining
    state.memory_queue_count = len(remaining)
    db.session.commit()


def search_memory(user_id: int, ai_id: int, query: str, top_k: int = 3) -> list[str]:
    """Return the top_k most similar memory contents for this (user, ai) pair."""
    rows = MemoryEntry.query.filter_by(user_id=user_id, ai_id=ai_id).all()
    if not rows:
        return []

    query_bytes = _embed(query)
    # skip rows whose stored embedding doesn't match the current embedder's
    # dimensionality (e.g. rows written under a different EMBEDDING_MODEL)
    usable = [r for r in rows if len(r.embedding) == len(query_bytes)]
    if len(usable) != len(rows):
        logger.warning('Skipping %d memory rows with mismatched embedding dims (user=%s ai=%s)',
                       len(rows) - len(usable), user_id, ai_id)
        rows = usable
        if not rows:
            return []

    query_vec = np.frombuffer(query_bytes, dtype=np.float32)
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
