"""AI model lookups and creation.

Ownership is the security boundary here: ``get_owned_ai`` is the single gate
every route that accepts an AI id from the URL/body must pass through (fixes the
/ai-settings IDOR). ``get_ai_model`` performs NO ownership check and is only
safe for template lookups.
"""

from src.extensions import db
from src.models.users import AIModel, AISettings


def get_ai_model(ai_id):
    """Fetch an AIModel with NO ownership check — only safe for template
    lookups. Routes taking an id from the URL must use get_owned_ai()."""
    return AIModel.query.filter_by(id=ai_id).first()


def get_owned_ai(user, ai_id):
    """Return the AIModel only if it exists and belongs to ``user``, else None.

    The single ownership gate for every route that accepts an AI id from the
    URL or request body (fixes the /ai-settings IDOR)."""
    ai_model = AIModel.query.filter_by(id=ai_id).first()
    if ai_model is None or ai_model not in user.ai_models:
        return None
    return ai_model


def create_ai_model(ai_name, ai_model_name, ai_prompt, ai_description, memory_chunk_size, profile_image_url=''):
    """Create a new AI model and its default settings.

    Input: ai_name, ai_model_name, ai_prompt, ai_description, memory_chunk_size (int).
    Output: ai_model (AIModel).
    """
    ai_model = AIModel(
        name=ai_name,
        model_name=ai_model_name,
        prompt=ai_prompt,
        description=ai_description,
        profile_image_url=profile_image_url,
    )
    db.session.add(ai_model)
    db.session.commit()

    # create AI settings with default settings
    ai_settings = AISettings(ai_model_id=ai_model.id, memory_chunk_size=memory_chunk_size)
    db.session.add(ai_settings)
    db.session.commit()

    return ai_model
