"""Unit tests for src/providers/gemini_provider.py (google-genai adapter).

google-genai IS installed, so we use the real ``google.genai.types`` module and
only mock the client at ``gemini_provider._get_client``. Fake response objects
(candidate/parts/usage) use SimpleNamespace to mimic the SDK's attribute shapes.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from google.genai import types

from src.providers import base
from src.providers import gemini_provider as gp


# --- fakes --------------------------------------------------------------------

def _fc_part(name, args):
    """A response part carrying a function_call (SDK-shaped)."""
    return SimpleNamespace(function_call=SimpleNamespace(name=name, args=args))


def _text_part(text='the reply'):
    """A response part carrying text (the adapter reads part.text directly —
    response.text warns/raises on candidates with only function_call parts)."""
    return SimpleNamespace(function_call=None, text=text)


def _fake_response(*, parts, finish_reason=types.FinishReason.STOP, text='',
                   prompt_tokens=10, candidate_tokens=5):
    candidate = SimpleNamespace(
        content=SimpleNamespace(parts=parts),
        finish_reason=finish_reason,
    )
    return SimpleNamespace(
        candidates=[candidate],
        text=text,
        usage_metadata=SimpleNamespace(prompt_token_count=prompt_tokens, candidates_token_count=candidate_tokens),
    )


@pytest.fixture
def fake_client(monkeypatch):
    client = MagicMock()
    client.models.generate_content.return_value = _fake_response(parts=[_text_part()], text='hi')
    monkeypatch.setattr(gp, '_get_client', lambda: client)
    return client


TOOLS = [{
    'name': 'memory_search',
    'description': 'search memory',
    'input_schema': {'type': 'object', 'properties': {'query': {'type': 'string'}}, 'required': ['query']},
}]


def _config(fake_client):
    return fake_client.models.generate_content.call_args.kwargs['config']


# --- config assembly ----------------------------------------------------------

def test_automatic_function_calling_disabled(fake_client):
    gp.GeminiProvider().generate(model='gemini-3-flash-preview', system='s',
                                 messages=[{'role': 'user', 'content': 'hi'}])
    assert _config(fake_client).automatic_function_calling.disable is True


def test_system_instruction_set(fake_client):
    gp.GeminiProvider().generate(model='gemini-3-flash-preview', system='SYS',
                                 messages=[{'role': 'user', 'content': 'hi'}])
    assert _config(fake_client).system_instruction == 'SYS'


def test_max_output_tokens_set(fake_client):
    gp.GeminiProvider().generate(model='gemini-3-flash-preview', system='s',
                                 messages=[{'role': 'user', 'content': 'hi'}], max_tokens=555)
    assert _config(fake_client).max_output_tokens == 555


def test_function_declarations_built_from_house_tools(fake_client):
    gp.GeminiProvider().generate(model='gemini-3-flash-preview', system='s',
                                 messages=[{'role': 'user', 'content': 'hi'}], tools=TOOLS)
    cfg = _config(fake_client)
    decls = cfg.tools[0].function_declarations
    assert [d.name for d in decls] == ['memory_search']
    assert decls[0].description == 'search memory'


def test_no_tools_when_none(fake_client):
    gp.GeminiProvider().generate(model='gemini-3-flash-preview', system='s',
                                 messages=[{'role': 'user', 'content': 'hi'}])
    assert _config(fake_client).tools is None


# --- content translation ------------------------------------------------------

def test_plain_string_becomes_user_content():
    contents = gp._to_contents([{'role': 'user', 'content': 'hello'}])
    assert len(contents) == 1
    assert contents[0].role == 'user'
    assert contents[0].parts[0].text == 'hello'


def test_assistant_role_maps_to_model():
    contents = gp._to_contents([{'role': 'assistant', 'content': 'reply'}])
    assert contents[0].role == 'model'


def test_tool_result_routed_via_function_response_with_name_from_id():
    messages = [{'role': 'user', 'content': [
        {'type': 'tool_result', 'tool_call_id': 'gemini::memory_search::0', 'content': 'the answer'},
    ]}]
    contents = gp._to_contents(messages)
    part = contents[0].parts[0]
    assert part.function_response.name == 'memory_search'
    assert part.function_response.response == {'result': 'the answer'}


def test_raw_passthrough_used_verbatim():
    raw = types.Content(role='model', parts=[types.Part(text='echoed')])
    contents = gp._to_contents([{'role': 'assistant', 'content': 'ignored', '_raw': raw}])
    assert contents == [raw]


# --- response normalization ---------------------------------------------------

def test_tool_call_synthesized_id(fake_client):
    fake_client.models.generate_content.return_value = _fake_response(
        parts=[_fc_part('memory_search', {'query': 'dogs'})],
        finish_reason=types.FinishReason.STOP)
    result = gp.GeminiProvider().generate(model='gemini-3-flash-preview', system='s',
                                          messages=[{'role': 'user', 'content': 'hi'}])
    assert result.stop_reason == base.STOP_TOOL_USE
    call = result.tool_calls[0]
    assert call.id == 'gemini::memory_search::0'
    assert call.name == 'memory_search'
    assert call.args == {'query': 'dogs'}


def test_synthesized_id_index_tracks_part_position(fake_client):
    # a text part precedes the function_call part -> index 1
    fake_client.models.generate_content.return_value = _fake_response(
        parts=[_text_part(), _fc_part('memory_search', {})])
    result = gp.GeminiProvider().generate(model='gemini-3-flash-preview', system='s',
                                          messages=[{'role': 'user', 'content': 'hi'}])
    assert result.tool_calls[0].id == 'gemini::memory_search::1'


@pytest.mark.parametrize('finish,expected', [
    (types.FinishReason.STOP, base.STOP_END_TURN),
    (types.FinishReason.MAX_TOKENS, base.STOP_MAX_TOKENS),
    (types.FinishReason.SAFETY, base.STOP_REFUSAL),
])
def test_finish_reason_mapping(fake_client, finish, expected):
    fake_client.models.generate_content.return_value = _fake_response(
        parts=[_text_part()], finish_reason=finish, text='x')
    result = gp.GeminiProvider().generate(model='gemini-3-flash-preview', system='s',
                                          messages=[{'role': 'user', 'content': 'hi'}])
    assert result.stop_reason == expected


def test_usage_and_text(fake_client):
    fake_client.models.generate_content.return_value = _fake_response(
        parts=[_text_part()], text='the reply', prompt_tokens=33, candidate_tokens=44)
    result = gp.GeminiProvider().generate(model='gemini-3-flash-preview', system='s',
                                          messages=[{'role': 'user', 'content': 'hi'}])
    assert result.text == 'the reply'
    assert result.usage.input_tokens == 33
    assert result.usage.output_tokens == 44
