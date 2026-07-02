"""Google Gemini adapter (NEW ``google-genai`` SDK).

Constraints honored (verified against docs, 2026-07):
- Everything except model/contents goes inside ``GenerateContentConfig``.
- Automatic function calling is DISABLED — we own the loop (maintainer:
  hand-rolled, no managed runners).
- ``function_call.args`` is already a dict (unlike OpenAI's JSON string).
- Gemini function calls carry NO id — we synthesize stable ids and keep the
  id→name mapping implicit (results are matched by name via
  ``Part.from_function_response``).
- Safety settings stay at SDK defaults (the legacy BLOCK_NONE overrides from
  ai_models.py are intentionally NOT carried over — see backlog LAUNCH-4).
"""

import logging
import os

from src.providers import base
from src.providers.base import LLMResult, ToolCall, Usage

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
    return _client


def _to_contents(messages: list[dict]):
    from google.genai import types

    contents = []
    for msg in messages:
        if msg.get('_raw') is not None:
            contents.append(msg['_raw'])
            continue
        role = 'model' if msg['role'] == 'assistant' else 'user'
        content = msg['content']
        if isinstance(content, str):
            contents.append(types.Content(role=role, parts=[types.Part(text=content)]))
            continue
        parts = []
        for block in content:
            if block['type'] == 'text':
                parts.append(types.Part(text=block['text']))
            elif block['type'] == 'tool_use':
                parts.append(types.Part.from_function_call(name=block['name'], args=block['args']))
            elif block['type'] == 'tool_result':
                # Gemini matches results by function NAME (no call ids); the
                # neutral id encodes it as 'gemini::<name>::<n>'.
                name = block['tool_call_id'].split('::')[1]
                parts.append(types.Part.from_function_response(name=name, response={'result': block['content']}))
        contents.append(types.Content(role=role, parts=parts))
    return contents


class GeminiProvider:
    def generate(self, *, model, system, messages, tools=None, max_tokens=2048, stream=False) -> LLMResult:
        from google.genai import types

        client = _get_client()
        config_kwargs = {
            'system_instruction': system,
            'max_output_tokens': max_tokens,
            'automatic_function_calling': types.AutomaticFunctionCallingConfig(disable=True),
        }
        if tools:
            declarations = [
                types.FunctionDeclaration(name=t['name'], description=t['description'], parameters=t['input_schema'])
                for t in tools
            ]
            config_kwargs['tools'] = [types.Tool(function_declarations=declarations)]

        response = client.models.generate_content(
            model=model,
            contents=_to_contents(messages),
            config=types.GenerateContentConfig(**config_kwargs),
        )

        candidate = response.candidates[0] if response.candidates else None
        tool_calls = []
        text_parts = []
        if candidate is not None:
            for i, part in enumerate(candidate.content.parts or []):
                fc = getattr(part, 'function_call', None)
                if fc:
                    tool_calls.append(ToolCall(id=f'gemini::{fc.name}::{i}', name=fc.name, args=dict(fc.args or {})))
                elif getattr(part, 'text', None):
                    text_parts.append(part.text)

        finish = str(getattr(candidate, 'finish_reason', 'STOP') or 'STOP')
        if tool_calls:
            stop_reason = base.STOP_TOOL_USE
        elif 'MAX_TOKENS' in finish:
            stop_reason = base.STOP_MAX_TOKENS
        elif 'SAFETY' in finish or 'PROHIBITED' in finish:
            stop_reason = base.STOP_REFUSAL
        else:
            stop_reason = base.STOP_END_TURN

        usage_meta = getattr(response, 'usage_metadata', None)
        usage = Usage(
            input_tokens=getattr(usage_meta, 'prompt_token_count', 0) or 0,
            output_tokens=getattr(usage_meta, 'candidates_token_count', 0) or 0,
        )
        # concatenate text parts explicitly — response.text warns/raises on
        # candidates that contain only function_call parts
        return LLMResult(
            text=''.join(text_parts),
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            usage=usage,
            model=model,
            raw=candidate.content if candidate else None,  # echoed back via _raw
        )
