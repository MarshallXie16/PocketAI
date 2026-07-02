"""AI ownership boundary tests.

get_owned_ai is the single gate every id-taking AI route must pass through
(the /ai-settings IDOR fix). These tests assert non-owners are denied and that
templates (is_template) are the only clonable AIs during onboarding.
"""

from src.models.users import AIModel
from src.services.ai_model_service import get_owned_ai


def test_get_owned_ai_none_for_non_owner(make_user, make_ai):
    owner = make_user(username='owner')
    intruder = make_user(username='intruder')
    ai = make_ai(owner=owner, name='OwnerAI', prompt='secret prompt {ai_name}')

    assert get_owned_ai(owner, ai.id) is ai
    assert get_owned_ai(intruder, ai.id) is None


def test_ai_settings_non_owner_redirected_without_leak(client, make_user, make_ai, login):
    owner = make_user(username='owner')
    make_user(username='intruder', password='pw')
    ai = make_ai(owner=owner, name='OwnerAI', prompt='TOP SECRET PROMPT {ai_name}')

    login('intruder', 'pw')
    resp = client.get(f'/ai-settings/{ai.id}')

    # non-owner is redirected (to profile), never shown the AI's settings page
    assert resp.status_code == 302
    assert '/profile' in resp.headers['Location']
    # no data leak in the redirect body
    assert b'TOP SECRET PROMPT' not in resp.data
    assert b'OwnerAI' not in resp.data


def test_change_ai_non_owner_rejected(client, make_user, make_ai, login):
    owner = make_user(username='owner')
    intruder = make_user(username='intruder', password='pw')
    ai = make_ai(owner=owner)

    login('intruder', 'pw')
    resp = client.get(f'/change-ai/{ai.id}')

    # redirected back to chat with no access granted
    assert resp.status_code == 302
    assert '/chat' in resp.headers['Location']
    assert intruder.settings.last_active_ai_id != ai.id


def test_onboarding_existing_refuses_non_template(client, make_user, make_ai, login):
    owner = make_user(username='owner')
    intruder = make_user(username='intruder', password='pw')
    private_ai = make_ai(owner=owner, is_template=False)

    login('intruder', 'pw')
    resp = client.post('/onboarding/ai/existing', data={'ai-id': private_ai.id})

    # cloning a non-template (someone else's private AI) is refused
    assert resp.status_code == 302
    assert '/onboarding/ai/existing' in resp.headers['Location']
    assert len(intruder.ai_models) == 0


def test_onboarding_existing_allows_template(client, make_user, make_ai, login):
    intruder = make_user(username='intruder', password='pw')
    template = make_ai(owner=None, name='TemplateAI', prompt='template {ai_name}', is_template=True)

    login('intruder', 'pw')
    resp = client.post('/onboarding/ai/existing', data={'ai-id': template.id})

    # cloning a template is allowed; the flow continues to onboarding step 3
    assert resp.status_code == 302
    assert '/onboarding/world' in resp.headers['Location']
    assert len(intruder.ai_models) == 1
    clone = intruder.ai_models[0]
    assert clone.id != template.id
    assert clone.name == 'TemplateAI'
    # the clone is a private copy, not itself a template
    assert AIModel.query.get(clone.id).is_template is False
