"""OpenAI adapter (SDK ``openai``, Responses API).

Constraints honored (verified against SDK 2.44 + docs, 2026-07):
- GPT-5-series reasoning models reject ``temperature``/``top_p`` (400) — never sent.
- Tool declarations are top-level ``{"type": "function", name, description,
  parameters, strict}`` (NOT nested under ``function``).
- ``function_call.arguments`` is a JSON STRING → ``json.loads``.
- Tool results go back as ``function_call_output`` items with the matching
  ``call_id``; the model's ``function_call`` items must be echoed back too
  (stashed under ``_raw`` on the neutral assistant message).
- Truncation surfaces as ``status == "incomplete"`` with
  ``incomplete_details.reason``.
"""

import json
import logging
import os

from src.providers import base
from src.providers.base import LLMResult, ToolCall, Usage

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
    return _client


def _to_tool_params(tools: list[dict]) -> list[dict]:
    """House format (Anthropic-style input_schema) → Responses API tools."""
    return [
        {
            'type': 'function',
            'name': t['name'],
            'description': t['description'],
            'parameters': t['input_schema'],
            'strict': False,  # house schemas don't set additionalProperties on every level
        }
        for t in tools
    ]


def _to_input_items(messages: list[dict]) -> list[dict]:
    """Neutral messages → Responses API input items."""
    items = []
    for msg in messages:
        if msg.get('_raw') is not None:
            items.extend(msg['_raw'])
            continue
        content = msg['content']
        if isinstance(content, str):
            items.append({'role': msg['role'], 'content': content})
            continue
        for block in content:
            if block['type'] == 'text':
                items.append({'role': msg['role'], 'content': block['text']})
            elif block['type'] == 'tool_use':
                items.append({
                    'type': 'function_call',
                    'call_id': block['id'],
                    'name': block['name'],
                    'arguments': json.dumps(block['args']),
                })
            elif block['type'] == 'tool_result':
                items.append({
                    'type': 'function_call_output',
                    'call_id': block['tool_call_id'],
                    'output': block['content'],
                })
    return items


class OpenAIProvider:
    def generate(self, *, model, system, messages, tools=None, max_tokens=2048, stream=False) -> LLMResult:
        client = _get_client()
        kwargs = {
            'model': model,
            'instructions': system,
            'input': _to_input_items(messages),
            'max_output_tokens': max_tokens,
            'store': False,  # stateless: we manage conversation state ourselves
        }
        if tools:
            kwargs['tools'] = _to_tool_params(tools)

        # Streaming deltas aren't surfaced to the UI yet; the SDK handles
        # long calls fine non-streaming on Responses, so collect directly.
        response = client.responses.create(**kwargs)

        tool_calls = []
        raw_items = []
        for item in response.output:
            if item.type == 'function_call':
                tool_calls.append(ToolCall(id=item.call_id, name=item.name, args=json.loads(item.arguments)))
                raw_items.append({
                    'type': 'function_call',
                    'call_id': item.call_id,
                    'name': item.name,
                    'arguments': item.arguments,
                })

        if tool_calls:
            stop_reason = base.STOP_TOOL_USE
        elif response.status == 'incomplete':
            reason = getattr(response.incomplete_details, 'reason', '')
            stop_reason = base.STOP_MAX_TOKENS if reason == 'max_output_tokens' else base.STOP_REFUSAL
        else:
            stop_reason = base.STOP_END_TURN

        text = response.output_text or ''
        if text:
            raw_items.insert(0, {'role': 'assistant', 'content': text})

        usage = Usage(
            input_tokens=getattr(response.usage, 'input_tokens', 0) or 0,
            output_tokens=getattr(response.usage, 'output_tokens', 0) or 0,
        )
        return LLMResult(
            text=text,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            usage=usage,
            model=model,
            raw=raw_items,  # echoed back via _raw in the next loop iteration
        )
