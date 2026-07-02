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


RETROSPECTIVE_PROMPT = '''You are {ai_name}, reflecting on a recent stretch of conversation with {username}. Extract what is worth remembering, as JSON.

Return EXACTLY this JSON shape (no markdown fences, no commentary):
{{
  "important": true/false,
  "situation": "what happened / what was discussed, specific enough to find later by describing it differently (1-2 sentences, from your perspective)",
  "emotional_tone": "one short phrase for how {username} seemed to feel, or null",
  "key_insight": "the single most useful thing you learned about {username} or their world, or null",
  "importance": 0.0-1.0,
  "entity_tags": ["specific people/places/events/topics mentioned"],
  "key_facts": [
    {{"fact_type": "commitment|event|person|preference|goal",
      "content": "one actionable fact, e.g. 'said they will sleep by 11pm tonight' or 'Amazon interview'",
      "due_at": "ISO-8601 UTC datetime if time-bound, else null"}}
  ],
  "tone_note": "a short note on how {username} likes to be talked to, ONLY if this snippet revealed one, else null"
}}

Guidance: importance 0.1-0.3 routine chat, 0.4-0.6 useful context, 0.7-0.9 significant life details or emotional moments. key_facts are ONLY concrete, actionable items — commitments the user made, upcoming events, people who matter. If nothing is worth remembering set "important": false and leave other fields null/empty. Current UTC time: {now_utc}.'''


def consolidate_and_save(user_id: int, ai_id: int, queue_lines: list[str],
                         ai_name: str, username: str) -> None:
    """Retrospective: turn a batch of exchanges into an episode + key facts.

    Runs on the background executor after a chat turn returns — the LLM
    extraction, embedding, and writes are all off the hot path. Adapted from
    the episodic-memory research design (situation/insight/importance/tags),
    with the consolidation step emitting structured KeyFact rows that power
    proactive follow-through.
    """
    import datetime as _dt
    import json

    from config import UTILITY_MODEL
    from src.providers.registry import get_provider

    now_utc = _dt.datetime.now(_dt.UTC)
    system = RETROSPECTIVE_PROMPT.replace('{ai_name}', ai_name).replace('{username}', username) \
                                 .replace('{now_utc}', now_utc.isoformat())
    # the prompt uses {{ }} for literal JSON braces; collapse them after token substitution
    system = system.replace('{{', '{').replace('}}', '}')

    result = get_provider(UTILITY_MODEL).generate(
        model=UTILITY_MODEL,
        system=system,
        messages=[{'role': 'user', 'content': 'Conversation snippet:\n' + '\n'.join(queue_lines)}],
        max_tokens=600,
    )

    raw = (result.text or '').strip()
    if raw.startswith('```'):
        raw = raw.strip('`').removeprefix('json').strip()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        logger.warning('Retrospective returned unparseable JSON (user=%s ai=%s): %.120s', user_id, ai_id, raw)
        data = {'important': False}
    # the model can legally return any JSON type — only a dict is usable
    if not isinstance(data, dict):
        data = {'important': False}

    if data.get('important') and isinstance(data.get('situation'), str):
        entity_tags = data.get('entity_tags')
        content = now_utc.strftime('%Y-%m-%d %H:%M ') + data['situation']
        save_memory(
            user_id, ai_id, content,
            emotional_tone=data.get('emotional_tone') if isinstance(data.get('emotional_tone'), str) else None,
            key_insight=data.get('key_insight') if isinstance(data.get('key_insight'), str) else None,
            importance=_coerce_importance(data.get('importance')),
            entity_tags=[str(t) for t in entity_tags[:10]] if isinstance(entity_tags, list) else [],
        )
        logger.info('Episode saved (user=%s ai=%s importance=%s)', user_id, ai_id, data.get('importance'))
    else:
        logger.info('Memory gate: nothing worth saving (user=%s ai=%s)', user_id, ai_id)

    _save_key_facts(user_id, ai_id, data.get('key_facts') or [])
    _save_tone_note(user_id, ai_id, data.get('tone_note'))

    # Success (or an intentional gate-drop): remove exactly the consumed
    # lines from the live queue. On exception we never reach here, the queue
    # stays intact, and the next full turn retries — no silent memory loss.
    _consume_queue_lines(user_id, ai_id, queue_lines)


def _coerce_importance(value, default=0.5) -> float:
    """LLMs return 'high', '0.7', 0.7, None... — clamp to a float in [0, 1]."""
    try:
        return min(max(float(value), 0.0), 1.0)
    except (TypeError, ValueError):
        return {'low': 0.2, 'medium': 0.5, 'high': 0.8}.get(str(value).strip().lower(), default)


def _save_key_facts(user_id: int, ai_id: int, facts) -> None:
    import datetime as _dt

    from src.models.relationship import KeyFact

    if not isinstance(facts, list):
        return
    valid_types = {'commitment', 'event', 'person', 'preference', 'goal'}
    for fact in facts[:5]:
        if not isinstance(fact, dict):
            continue
        # newline-stripped + capped: this text lands in the system prompt later
        content = ' '.join(str(fact.get('content') or '').split())[:300]
        fact_type = str(fact.get('fact_type') or '').strip()
        if not content or fact_type not in valid_types:
            continue
        # dedupe on exact content for this pair
        exists = KeyFact.query.filter_by(user_id=user_id, ai_id=ai_id, content=content).first()
        if exists:
            continue
        due_at = None
        if fact.get('due_at'):
            try:
                due_at = _dt.datetime.fromisoformat(str(fact['due_at']).replace('Z', '+00:00'))
            except ValueError:
                pass
        db.session.add(KeyFact(user_id=user_id, ai_id=ai_id, fact_type=fact_type,
                               content=content, due_at=due_at))
    db.session.commit()


def _save_tone_note(user_id: int, ai_id: int, note) -> None:
    from src.models.relationship import RelationshipState

    if not note or not isinstance(note, str):
        return
    note = ' '.join(note.split())[:200]   # single line, capped — lands in the system prompt
    state = RelationshipState.get_or_create(user_id, ai_id)
    prefs = list(state.tone_prefs or [])
    if note not in prefs:
        prefs.append(note)
        state.tone_prefs = prefs[-10:]   # keep the latest handful
        db.session.commit()


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
    similarity = matrix @ query_vec / np.where(norms == 0, 1.0, norms)

    # Composite recall (episodic-memory design): similarity dominates,
    # recency/reinforcement/importance modulate — memories that matter and
    # get used stay vivid; trivia fades.
    now = datetime.datetime.now(datetime.UTC)

    def _days_since(dt):
        if dt is None:
            return 365.0
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.UTC)
        return max((now - dt).total_seconds() / 86400.0, 0.0)

    recency = np.array([np.exp(-0.023 * _days_since(r.last_accessed)) for r in rows])  # ~30d half-life
    reinforcement = np.array([min(1.0 + 0.1 * np.log1p(r.access_count or 0), 1.5) for r in rows])
    importance = np.array([r.importance if r.importance is not None else 0.5 for r in rows])

    scores = similarity * 0.6 + recency * 0.15 + reinforcement * 0.10 + importance * 0.15

    ranked = sorted(zip(scores, rows), key=lambda pair: -pair[0])[:top_k]

    for _, row in ranked:
        row.last_accessed = now
        row.access_count += 1
    db.session.commit()

    return [
        row.content + (f' — insight: {row.key_insight}' if row.key_insight else '')
        for _, row in ranked
    ]
