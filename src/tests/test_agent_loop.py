"""Tests for the hand-rolled agent loop (src/ai/agent.py).

A scripted FakeProvider replaces the real provider (patched at
``agent.get_provider``) and records the messages it is handed each turn. Tool
dispatch is patched at ``agent.tool_registry.dispatch`` so no real tools run.
No SDKs, DB, or app context are touched.
"""

import copy

from src.ai import agent
from src.providers import base
from src.providers.base import LLMResult, ToolCall, Usage


class FakeProvider:
    """Returns scripted LLMResults in order; deep-copies each ``messages`` list
    it receives so later mutation by the loop doesn't corrupt the record."""

    def __init__(self, results):
        self._results = list(results)
        self.calls = []  # list of dicts: {messages, tools, max_tokens}

    def generate(self, *, model, system, messages, tools=None, max_tokens=2048, stream=False):
        self.calls.append({'messages': copy.deepcopy(messages), 'tools': tools, 'max_tokens': max_tokens})
        if len(self._results) == 1:
            return self._results[0]
        return self._results.pop(0)


def _tool_result(*calls, text='', input_tokens=10, output_tokens=5):
    return LLMResult(text=text, tool_calls=list(calls), stop_reason=base.STOP_TOOL_USE,
                     usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens), model='m', raw='RAW')


def _final(text, *, stop_reason=base.STOP_END_TURN, input_tokens=7, output_tokens=3):
    return LLMResult(text=text, tool_calls=[], stop_reason=stop_reason,
                     usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens), model='m')


def _install(monkeypatch, provider):
    monkeypatch.setattr(agent, 'get_provider', lambda model: provider)


BASE_KW = dict(
    model_name='claude-haiku-4-5', persona_prompt='You are {ai_name}.', ai_name='Aria',
    username='sam', conversation_mode='conversation', system_info='now', user_id=42, ai_id=7,
)


# --- (a) single tool call then finish ----------------------------------------

def test_single_tool_call_then_end_turn(monkeypatch):
    provider = FakeProvider([
        _tool_result(ToolCall(id='toolu_1', name='memory_search', args={'query': 'dogs'}),
                     input_tokens=100, output_tokens=20),
        _final('here is your answer', input_tokens=50, output_tokens=10),
    ])
    _install(monkeypatch, provider)

    dispatched = {}

    def fake_dispatch(name, args, *, user_id, ai_id, user_timezone='UTC'):
        dispatched.update(name=name, args=args, user_id=user_id, ai_id=ai_id, user_timezone=user_timezone)
        return 'tool output text'

    monkeypatch.setattr(agent.tool_registry, 'dispatch', fake_dispatch)

    turn = agent.run_turn(history=[{'role': 'user', 'content': 'what do you remember?'}],
                          user_timezone='America/New_York', **BASE_KW)

    # dispatch called once, correctly scoped
    assert dispatched == {'name': 'memory_search', 'args': {'query': 'dogs'},
                          'user_id': 42, 'ai_id': 7, 'user_timezone': 'America/New_York'}
    # final text surfaced
    assert turn.text == 'here is your answer'
    assert turn.tools_used == ['memory_search']
    # token totals summed across both generate calls
    assert turn.total_input_tokens == 150
    assert turn.total_output_tokens == 30

    # second generate call received the tool_result fed back with matching id
    second_messages = provider.calls[1]['messages']
    result_block = second_messages[-1]['content'][0]
    assert result_block['type'] == 'tool_result'
    assert result_block['tool_call_id'] == 'toolu_1'
    assert result_block['content'] == 'tool output text'
    # the assistant turn preceding it carried the raw passthrough for echo
    assert second_messages[-2]['_raw'] == 'RAW'


# --- (b) runaway tool loop hits the guard ------------------------------------

def test_runaway_tool_loop_stops_and_makes_final_call(monkeypatch):
    # always asks for a tool -> never terminates on its own
    forever = _tool_result(ToolCall(id='t', name='memory_search', args={'query': 'x'}))
    provider = FakeProvider([forever])  # single result reused every call
    _install(monkeypatch, provider)
    monkeypatch.setattr(agent.tool_registry, 'dispatch', lambda *a, **k: 'out')

    agent.run_turn(history=[{'role': 'user', 'content': 'go'}], **BASE_KW)

    # MAX_TOOL_ITERATIONS loop calls + 1 final no-tools call
    assert len(provider.calls) == agent.MAX_TOOL_ITERATIONS + 1
    # the final call disables tools
    assert provider.calls[-1]['tools'] is None
    # loop iterations each passed the real tool set
    assert provider.calls[0]['tools'] is not None


# --- (c) refusal with empty text ---------------------------------------------

def test_refusal_empty_text_falls_back(monkeypatch):
    provider = FakeProvider([_final('', stop_reason=base.STOP_REFUSAL)])
    _install(monkeypatch, provider)
    monkeypatch.setattr(agent.tool_registry, 'dispatch', lambda *a, **k: 'out')

    turn = agent.run_turn(history=[{'role': 'user', 'content': 'bad thing'}], **BASE_KW)

    assert turn.stop_reason == base.STOP_REFUSAL
    assert turn.text == "I'd rather not go there — want to talk about something else?"


# --- (d) extra_context becomes a distinct block ------------------------------

def test_extra_context_becomes_distinct_block(monkeypatch):
    provider = FakeProvider([_final('ok')])
    _install(monkeypatch, provider)
    monkeypatch.setattr(agent.tool_registry, 'dispatch', lambda *a, **k: 'out')

    agent.run_turn(history=[{'role': 'user', 'content': 'my actual words'}],
                   extra_context='earlier summary text', **BASE_KW)

    sent = provider.calls[0]['messages'][-1]
    assert sent['role'] == 'user'
    assert isinstance(sent['content'], list)
    assert len(sent['content']) == 2
    # context is its own block; the user's words are untouched in a second block
    assert 'earlier summary text' in sent['content'][0]['text']
    assert sent['content'][1]['text'] == 'my actual words'


def test_no_extra_context_leaves_string_content(monkeypatch):
    provider = FakeProvider([_final('ok')])
    _install(monkeypatch, provider)
    monkeypatch.setattr(agent.tool_registry, 'dispatch', lambda *a, **k: 'out')

    agent.run_turn(history=[{'role': 'user', 'content': 'plain words'}], **BASE_KW)

    assert provider.calls[0]['messages'][-1]['content'] == 'plain words'
