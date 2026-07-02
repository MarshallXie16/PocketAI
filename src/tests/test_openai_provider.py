"""Unit tests for src/providers/openai_provider.py (Responses API adapter).

The openai SDK client is patched at ``openai_provider._get_client`` so nothing
needs OPENAI_API_KEY. Fake Responses objects mimic the ``output`` item / usage
shapes from the provider-API brief.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.providers import base
from src.providers import openai_provider as op


# --- fakes --------------------------------------------------------------------

def _function_call_item(call_id, name, arguments):
    return SimpleNamespace(type='function_call', call_id=call_id, name=name, arguments=arguments)


def _fake_response(*, output=None, output_text='', status='completed',
                   incomplete_reason=None, input_tokens=10, output_tokens=5):
    incomplete = SimpleNamespace(reason=incomplete_reason) if incomplete_reason is not None else None
    return SimpleNamespace(
        output=output or [],
        output_text=output_text,
        status=status,
        incomplete_details=incomplete,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        id='resp_1',
    )


@pytest.fixture
def fake_client(monkeypatch):
    client = MagicMock()
    client.responses.create.return_value = _fake_response(output_text='hello')
    monkeypatch.setattr(op, '_get_client', lambda: client)
    return client


TOOLS = [{
    'name': 'memory_search',
    'description': 'search memory',
    'input_schema': {'type': 'object', 'properties': {'query': {'type': 'string'}}, 'required': ['query']},
}]


# --- request kwargs -----------------------------------------------------------

def test_instructions_is_system(fake_client):
    op.OpenAIProvider().generate(model='gpt-5.2', system='SYS',
                                 messages=[{'role': 'user', 'content': 'hi'}])
    assert fake_client.responses.create.call_args.kwargs['instructions'] == 'SYS'


def test_store_false(fake_client):
    op.OpenAIProvider().generate(model='gpt-5.2', system='s',
                                 messages=[{'role': 'user', 'content': 'hi'}])
    assert fake_client.responses.create.call_args.kwargs['store'] is False


def test_no_sampling_params_ever(fake_client):
    op.OpenAIProvider().generate(model='gpt-5.2', system='s',
                                 messages=[{'role': 'user', 'content': 'hi'}])
    kwargs = fake_client.responses.create.call_args.kwargs
    assert 'temperature' not in kwargs
    assert 'top_p' not in kwargs


def test_max_output_tokens_passed(fake_client):
    op.OpenAIProvider().generate(model='gpt-5.2', system='s',
                                 messages=[{'role': 'user', 'content': 'hi'}],
                                 max_tokens=777)
    assert fake_client.responses.create.call_args.kwargs['max_output_tokens'] == 777


# --- tool declaration conversion ---------------------------------------------

def test_tool_declaration_conversion():
    out = op._to_tool_params(TOOLS)
    assert out == [{
        'type': 'function',
        'name': 'memory_search',
        'description': 'search memory',
        'parameters': TOOLS[0]['input_schema'],
        'strict': False,
    }]


# --- input item translation ---------------------------------------------------

def test_function_call_input_item_serializes_args():
    messages = [{'role': 'assistant', 'content': [
        {'type': 'tool_use', 'id': 'call_1', 'name': 'memory_search', 'args': {'query': 'x'}},
    ]}]
    items = op._to_input_items(messages)
    assert items[0]['type'] == 'function_call'
    assert items[0]['call_id'] == 'call_1'
    assert items[0]['name'] == 'memory_search'
    assert json.loads(items[0]['arguments']) == {'query': 'x'}


def test_tool_result_becomes_function_call_output():
    messages = [{'role': 'user', 'content': [
        {'type': 'tool_result', 'tool_call_id': 'call_1', 'content': 'the answer'},
    ]}]
    items = op._to_input_items(messages)
    assert items[0] == {'type': 'function_call_output', 'call_id': 'call_1', 'output': 'the answer'}


def test_raw_items_extended_verbatim():
    raw = [{'type': 'function_call', 'call_id': 'c1', 'name': 'n', 'arguments': '{}'}]
    messages = [{'role': 'assistant', 'content': [], '_raw': raw}]
    items = op._to_input_items(messages)
    assert items == raw


# --- response normalization ---------------------------------------------------

def test_function_call_parsed_into_toolcall(fake_client):
    fake_client.responses.create.return_value = _fake_response(
        output=[_function_call_item('call_7', 'memory_search', '{"query": "dogs"}')])
    result = op.OpenAIProvider().generate(model='gpt-5.2', system='s',
                                          messages=[{'role': 'user', 'content': 'hi'}])
    assert result.stop_reason == base.STOP_TOOL_USE
    call = result.tool_calls[0]
    assert (call.id, call.name, call.args) == ('call_7', 'memory_search', {'query': 'dogs'})


def test_echoed_function_call_in_raw(fake_client):
    fake_client.responses.create.return_value = _fake_response(
        output=[_function_call_item('call_7', 'memory_search', '{"query": "dogs"}')])
    result = op.OpenAIProvider().generate(model='gpt-5.2', system='s',
                                          messages=[{'role': 'user', 'content': 'hi'}])
    # the model's function_call is echoed back verbatim for the next iteration
    assert {'type': 'function_call', 'call_id': 'call_7', 'name': 'memory_search',
            'arguments': '{"query": "dogs"}'} in result.raw


def test_text_response_prepends_assistant_raw(fake_client):
    fake_client.responses.create.return_value = _fake_response(output_text='the reply')
    result = op.OpenAIProvider().generate(model='gpt-5.2', system='s',
                                          messages=[{'role': 'user', 'content': 'hi'}])
    assert result.text == 'the reply'
    assert result.raw[0] == {'role': 'assistant', 'content': 'the reply'}
    assert result.stop_reason == base.STOP_END_TURN


def test_incomplete_max_output_tokens_maps_to_max_tokens(fake_client):
    fake_client.responses.create.return_value = _fake_response(
        output_text='trunc', status='incomplete', incomplete_reason='max_output_tokens')
    result = op.OpenAIProvider().generate(model='gpt-5.2', system='s',
                                          messages=[{'role': 'user', 'content': 'hi'}])
    assert result.stop_reason == base.STOP_MAX_TOKENS


def test_incomplete_content_filter_maps_to_refusal(fake_client):
    fake_client.responses.create.return_value = _fake_response(
        output_text='', status='incomplete', incomplete_reason='content_filter')
    result = op.OpenAIProvider().generate(model='gpt-5.2', system='s',
                                          messages=[{'role': 'user', 'content': 'hi'}])
    assert result.stop_reason == base.STOP_REFUSAL


def test_usage_fields(fake_client):
    fake_client.responses.create.return_value = _fake_response(
        output_text='x', input_tokens=42, output_tokens=99)
    result = op.OpenAIProvider().generate(model='gpt-5.2', system='s',
                                          messages=[{'role': 'user', 'content': 'hi'}])
    assert result.usage.input_tokens == 42
    assert result.usage.output_tokens == 99
    assert result.model == 'gpt-5.2'
