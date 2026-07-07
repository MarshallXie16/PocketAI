"""Long-term episodic memory model.

Defines MemoryEntry: one embedded memory per (user, ai) pair, with the vector
stored as raw float32 bytes and ranked by in-Python cosine similarity.
"""

import datetime

from src.extensions import db


class MemoryEntry(db.Model):
    """Long-term memory row for a (user, ai) pair.

    The embedding is stored as raw float32 bytes and ranked by in-Python
    cosine similarity (see src/ai/memory.py). This works identically on
    SQLite (dev) and Postgres; pgvector becomes a drop-in ranking
    optimization once a managed Postgres exists (deployment is deferred).

    Phase 4a extends this into full episodic memory (importance, tags,
    access tracking) — columns are already here so the Alembic baseline
    (LAUNCH-5) captures the final shape.
    """

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    ai_id = db.Column(db.Integer, db.ForeignKey('ai_model.id', ondelete='CASCADE'), nullable=False)
    content = db.Column(db.Text, nullable=False)          # the remembered text (summary / episode)
    embedding = db.Column(db.LargeBinary, nullable=False)  # float32 bytes, len = 4 * dims
    # --- episodic fields (Phase 4a; defaults keep Phase-3 writes valid) ---
    emotional_tone = db.Column(db.String(64), nullable=True)
    key_insight = db.Column(db.Text, nullable=True)
    importance = db.Column(db.Float, default=0.5, nullable=False)
    entity_tags = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime, index=True, default=lambda: datetime.datetime.now(datetime.UTC))
    last_accessed = db.Column(db.DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    access_count = db.Column(db.Integer, default=0, nullable=False)

    __table_args__ = (db.Index('ix_memory_entry_user_ai', 'user_id', 'ai_id'),)
