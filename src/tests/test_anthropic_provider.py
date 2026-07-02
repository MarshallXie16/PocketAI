"""Unit tests for src/providers/anthropic_provider.py.

The anthropic SDK client is patched at the module boundary
(``anthropic_provider._get_client``) so nothing constructs a real client or
needs ANTHROPIC_API_KEY. Fake SDK response objects use SimpleNamespace to mimic
the block/usage attribute shapes documented in the provider-API brief.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.providers import anthropic_provider as ap
from src.providers import base


# --- fakes --------------------------------------------------------------------

def _text_block(text):
    return SimpleNamespace(type='text', text=text)


def _tool_use_block(id, name, input):
    return SimpleNamespace(type='tool_use', id=id, name=name, input=input)


def _fake_response(*, content, stop_reason='end_turn', input_tokens=10,
                   output_tokens=5, model='claude-opus-4-8'):
    return SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        model=model,
    )


@pytest.fixture
def fake_client(monkeypatch):
    """A MagicMock anthropic client wired into the provider module.

    ``messages.create`` returns a default text response; individual tests can
    override ``.return_value``. Streaming is wired as a context manager.
    """
    client = MagicMock()
    default = _fake_response(content=[_text_block('hi')])
    client.messages.create.return_value = default
    client.messages.stream.return_value.__enter__.return_value.get_final_message.return_value = default
    monkeypatch.setattr(ap, '_get_client', lambda: client)
    return client


TOOLS = [{
    'name': 'memory_search',
    'description': 'search memory',
    'input_schema': {'type': 'object', 'properties': {'query': {'type': 'string'}}, 'required': ['query']},
}]


# --- sampling params never sent ----------------------------------------------

@pytest.mark.parametrize('model', ['claude-opus-4-8', 'claude-sonnet-4-6', 'claude-haiku-4-5'])
def test_no_sampling_params_ever(fake_client, model):
    ap.AnthropicProvider().generate(model=model, system='s',
                                    messages=[{'role': 'user', 'content': 'hi'}])
    kwargs = fake_client.messages.create.call_args.kwargs
    for banned in ('temperature', 'top_p', 'top_k'):
        assert banned not in kwargs


# --- adaptive thinking only on opus ------------------------------------------

def test_thinking_present_for_opus(fake_client):
    ap.AnthropicProvider().generate(model='claude-opus-4-8', system='s',
                                    messages=[{'role': 'user', 'content': 'hi'}])
    kwargs = fake_client.messages.create.call_args.kwargs
    assert kwargs['thinking'] == {'type': 'adaptive'}


@pytest.mark.parametrize('model', ['claude-sonnet-4-6', 'claude-haiku-4-5'])
def test_thinking_absent_for_non_opus(fake_client, model):
    ap.AnthropicProvider().generate(model=model, system='s',
                                    messages=[{'role': 'user', 'content': 'hi'}])
    kwargs = fake_client.messages.create.call_args.kwargs
    assert 'thinking' not in kwargs


# --- max_tokens + tools verbatim ---------------------------------------------

def test_max_tokens_passed(fake_client):
    ap.AnthropicProvider().generate(model='claude-haiku-4-5', system='s',
                                    messages=[{'role': 'user', 'content': 'hi'}],
                                    max_tokens=1234)
    assert fake_client.messages.create.call_args.kwargs['max_tokens'] == 1234


def test_tools_passed_through_verbatim(fake_client):
    ap.AnthropicProvider().generate(model='claude-haiku-4-5', system='s',
                                    messages=[{'role': 'user', 'content': 'hi'}],
                                    tools=TOOLS)
    # house format IS Anthropic format: passed through unchanged
    assert fake_client.messages.create.call_args.kwargs['tools'] is TOOLS


def test_system_passed(fake_client):
    ap.AnthropicProvider().generate(model='claude-haiku-4-5', system='SYS',
                                    messages=[{'role': 'user', 'content': 'hi'}])
    assert fake_client.messages.create.call_args.kwargs['system'] == 'SYS'


def test_no_tools_key_when_none(fake_client):
    ap.AnthropicProvider().generate(model='claude-haiku-4-5', system='s',
                                    messages=[{'role': 'user', 'content': 'hi'}])
    assert 'tools' not in fake_client.messages.create.call_args.kwargs


# --- message translation ------------------------------------------------------

def test_translate_plain_string():
    out = ap._to_anthropic_messages([{'role': 'user', 'content': 'hello'}])
    assert out == [{'role': 'user', 'content': 'hello'}]


def test_translate_tool_use_and_result_blocks():
    messages = [
        {'role': 'assistant', 'content': [
            {'type': 'text', 'text': 'let me check'},
            {'type': 'tool_use', 'id': 'toolu_1', 'name': 'memory_search', 'args': {'query': 'x'}},
        ]},
        {'role': 'user', 'content': [
            {'type': 'tool_result', 'tool_call_id': 'toolu_1', 'content': 'found it'},
        ]},
    ]
    out = ap._to_anthropic_messages(messages)
    asst = out[0]['content']
    assert asst[0] == {'type': 'text', 'text': 'let me check'}
    assert asst[1] == {'type': 'tool_use', 'id': 'toolu_1', 'name': 'memory_search', 'input': {'query': 'x'}}
    result = out[1]['content'][0]
    assert result == {'type': 'tool_result', 'tool_use_id': 'toolu_1', 'content': 'found it'}


def test_translate_raw_passthrough_used_verbatim():
    raw = [SimpleNamespace(type='thinking', signature='sig')]
    messages = [{'role': 'assistant', 'content': [{'type': 'text', 'text': 'ignored'}], '_raw': raw}]
    out = ap._to_anthropic_messages(messages)
    # _raw is echoed unchanged, ignoring the neutral 'content'
    assert out == [{'role': 'assistant', 'content': raw}]


# --- response normalization ---------------------------------------------------

def test_response_text_concatenation(fake_client):
    fake_client.messages.create.return_value = _fake_response(
        content=[_text_block('Hello '), _text_block('world')])
    result = ap.AnthropicProvider().generate(model='claude-haiku-4-5', system='s',
                                             messages=[{'role': 'user', 'content': 'hi'}])
    assert result.text == 'Hello world'


def test_response_tool_call_extraction(fake_client):
    fake_client.messages.create.return_value = _fake_response(
        content=[_text_block('sure'), _tool_use_block('toolu_9', 'memory_search', {'query': 'dogs'})],
        stop_reason='tool_use')
    result = ap.AnthropicProvider().generate(model='claude-haiku-4-5', system='s',
                                             messages=[{'role': 'user', 'content': 'hi'}])
    assert len(result.tool_calls) == 1
    call = result.tool_calls[0]
    assert (call.id, call.name, call.args) == ('toolu_9', 'memory_search', {'query': 'dogs'})
    assert result.stop_reason == base.STOP_TOOL_USE


@pytest.mark.parametrize('raw,expected', [
    ('end_turn', base.STOP_END_TURN),
    ('tool_use', base.STOP_TOOL_USE),
    ('max_tokens', base.STOP_MAX_TOKENS),
    ('refusal', base.STOP_REFUSAL),
    ('stop_sequence', base.STOP_END_TURN),
    ('pause_turn', base.STOP_END_TURN),
    ('something_new', base.STOP_END_TURN),  # unknown -> end_turn default
])
def test_stop_reason_mapping(fake_client, raw, expected):
    fake_client.messages.create.return_value = _fake_response(
        content=[_text_block('x')], stop_reason=raw)
    result = ap.AnthropicProvider().generate(model='claude-haiku-4-5', system='s',
                                             messages=[{'role': 'user', 'content': 'hi'}])
    assert result.stop_reason == expected


def test_usage_and_model_fields(fake_client):
    fake_client.messages.create.return_value = _fake_response(
        content=[_text_block('x')], input_tokens=111, output_tokens=222, model='claude-opus-4-8')
    result = ap.AnthropicProvider().generate(model='claude-opus-4-8', system='s',
                                             messages=[{'role': 'user', 'content': 'hi'}])
    assert result.usage.input_tokens == 111
    assert result.usage.output_tokens == 222
    assert result.model == 'claude-opus-4-8'
    # raw stashes the content list for _raw echo (thinking continuity)
    assert result.raw == fake_client.messages.create.return_value.content


# --- streaming path -----------------------------------------------------------

def test_streaming_chosen_when_max_tokens_over_threshold(fake_client):
    streamed = _fake_response(content=[_text_block('streamed')])
    fake_client.messages.stream.return_value.__enter__.return_value.get_final_message.return_value = streamed
    result = ap.AnthropicProvider().generate(model='claude-haiku-4-5', system='s',
                                             messages=[{'role': 'user', 'content': 'hi'}],
                                             max_tokens=ap._STREAM_THRESHOLD_TOKENS + 1)
    fake_client.messages.stream.assert_called_once()
    fake_client.messages.create.assert_not_called()
    assert result.text == 'streamed'


def test_streaming_chosen_when_stream_flag(fake_client):
    ap.AnthropicProvider().generate(model='claude-haiku-4-5', system='s',
                                    messages=[{'role': 'user', 'content': 'hi'}],
                                    stream=True)
    fake_client.messages.stream.assert_called_once()
    fake_client.messages.create.assert_not_called()


def test_nonstreaming_below_threshold(fake_client):
    ap.AnthropicProvider().generate(model='claude-haiku-4-5', system='s',
                                    messages=[{'role': 'user', 'content': 'hi'}],
                                    max_tokens=ap._STREAM_THRESHOLD_TOKENS)
    fake_client.messages.create.assert_called_once()
    fake_client.messages.stream.assert_not_called()
