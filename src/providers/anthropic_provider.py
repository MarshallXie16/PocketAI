"""Anthropic adapter (SDK ``anthropic``, Messages API).

Constraints honored here (verified against SDK 0.115 + docs, 2026-07):
- ``max_tokens`` is required on every call.
- NEVER send ``temperature``/``top_p``/``top_k`` — they 400 on Opus 4.8; we
  omit them for all Claude models and steer behavior via prompting.
- ``thinking={"type": "adaptive"}`` on Opus 4.8 only.
- Streaming is required for large ``max_tokens``; we stream above a threshold
  and collect the final message.
- With thinking enabled, prior assistant turns must be echoed back with
  their thinking blocks unmodified — adapters reuse the raw content stashed
  on the neutral message under ``_raw`` (set by this adapter).
"""

import logging
import os

from src.providers import base
from src.providers.base import LLMResult, ToolCall, Usage

logger = logging.getLogger(__name__)

_STREAM_THRESHOLD_TOKENS = 8192
_ADAPTIVE_THINKING_MODELS = {'claude-opus-4-8'}

_STOP_REASON_MAP = {
    'end_turn': base.STOP_END_TURN,
    'stop_sequence': base.STOP_END_TURN,
    'pause_turn': base.STOP_END_TURN,
    'tool_use': base.STOP_TOOL_USE,
    'max_tokens': base.STOP_MAX_TOKENS,
    'refusal': base.STOP_REFUSAL,
}

_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
    return _client


def _to_anthropic_messages(messages: list[dict]) -> list[dict]:
    """Translate neutral messages to Anthropic wire format.

    Assistant turns produced by this adapter carry the raw SDK content under
    ``_raw`` — reuse it verbatim (preserves thinking-block signatures)."""
    out = []
    for msg in messages:
        if msg.get('_raw') is not None:
            out.append({'role': msg['role'], 'content': msg['_raw']})
            continue
        content = msg['content']
        if isinstance(content, str):
            out.append({'role': msg['role'], 'content': content})
            continue
        blocks = []
        for block in content:
            if block['type'] == 'text':
                blocks.append({'type': 'text', 'text': block['text']})
            elif block['type'] == 'tool_use':
                blocks.append({'type': 'tool_use', 'id': block['id'], 'name': block['name'], 'input': block['args']})
            elif block['type'] == 'tool_result':
                blocks.append({'type': 'tool_result', 'tool_use_id': block['tool_call_id'], 'content': block['content']})
        out.append({'role': msg['role'], 'content': blocks})
    return out


class AnthropicProvider:
    def generate(self, *, model, system, messages, tools=None, max_tokens=2048, stream=False) -> LLMResult:
        client = _get_client()
        kwargs = {
            'model': model,
            'max_tokens': max_tokens,
            'system': system,
            'messages': _to_anthropic_messages(messages),
        }
        if tools:
            # Anthropic's format IS the house format: {name, description, input_schema}
            kwargs['tools'] = tools
        if model in _ADAPTIVE_THINKING_MODELS:
            kwargs['thinking'] = {'type': 'adaptive'}

        if stream or max_tokens > _STREAM_THRESHOLD_TOKENS:
            with client.messages.stream(**kwargs) as s:
                response = s.get_final_message()
        else:
            response = client.messages.create(**kwargs)

        text = ''.join(b.text for b in response.content if b.type == 'text')
        tool_calls = [
            ToolCall(id=b.id, name=b.name, args=dict(b.input))
            for b in response.content if b.type == 'tool_use'
        ]
        return LLMResult(
            text=text,
            tool_calls=tool_calls,
            stop_reason=_STOP_REASON_MAP.get(response.stop_reason, base.STOP_END_TURN),
            usage=Usage(input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens),
            model=response.model,
            raw=response.content,  # stash for _raw echo (thinking-block continuity)
        )
