"""The companion agent loop — hand-rolled native tool use.

Replaces the legacy context_analyzer cascade (a 4–5-hop LLM router on the
deprecated ``functions=`` API) with a single loop on the persona model:
generate → execute any requested tools (ownership-scoped) → feed results
back → repeat until the model finishes. One model, one conversation, no
managed agent frameworks.
"""

import logging
from dataclasses import dataclass, field

from src.ai import tools as tool_registry
from src.ai.prompts import build_system_prompt
from src.providers import base
from src.providers.registry import calculate_cost, get_provider, resolve_model

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 6
DEFAULT_MAX_TOKENS = 2048


@dataclass
class AgentTurn:
    """Outcome of one user turn through the agent loop."""

    text: str
    tools_used: list[str] = field(default_factory=list)
    tool_context: str = ''          # concatenated tool outputs (carried to the next turn)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    stop_reason: str = base.STOP_END_TURN


def run_turn(*, model_name: str, persona_prompt: str, ai_name: str, username: str,
             conversation_mode: str, system_info: str, history: list[dict],
             user_id: int, ai_id: int, user_timezone: str = 'UTC',
             relationship_block: str = '', extra_context: str = '') -> AgentTurn:
    """Run one full agent turn. ``history`` is neutral-format messages ending
    with the latest user message. ``extra_context`` (e.g. the rolling summary
    from short-term memory) is passed as a distinct block on the last user
    message, never string-concatenated into their words."""
    model = resolve_model(model_name)
    provider = get_provider(model)
    system = build_system_prompt(persona_prompt, ai_name, username,
                                 conversation_mode, system_info, relationship_block)

    messages = [dict(m) for m in history]
    if extra_context and messages and messages[-1]['role'] == 'user':
        last = messages[-1]
        text = last['content'] if isinstance(last['content'], str) else ''
        last['content'] = [
            {'type': 'text', 'text': f'[Context from earlier conversation — may be irrelevant]\n{extra_context}'},
            {'type': 'text', 'text': text},
        ]

    turn = AgentTurn(text='')
    for iteration in range(MAX_TOOL_ITERATIONS):
        result = provider.generate(
            model=model,
            system=system,
            messages=messages,
            tools=tool_registry.TOOLS,
            max_tokens=DEFAULT_MAX_TOKENS,
        )
        turn.total_input_tokens += result.usage.input_tokens
        turn.total_output_tokens += result.usage.output_tokens
        turn.stop_reason = result.stop_reason

        if result.stop_reason != base.STOP_TOOL_USE:
            turn.text = result.text
            break

        # Echo the assistant turn (raw content preserves provider-specific
        # blocks, e.g. Anthropic thinking signatures), then run each tool.
        assistant_blocks = (
            [{'type': 'text', 'text': result.text}] if result.text else []
        ) + [
            {'type': 'tool_use', 'id': c.id, 'name': c.name, 'args': c.args}
            for c in result.tool_calls
        ]
        messages.append({'role': 'assistant', 'content': assistant_blocks, '_raw': result.raw})

        result_blocks = []
        for call in result.tool_calls:
            logger.info('Tool call: %s(%s) [user=%s ai=%s]', call.name, list(call.args), user_id, ai_id)
            output = tool_registry.dispatch(call.name, call.args, user_id=user_id,
                                            ai_id=ai_id, user_timezone=user_timezone)
            turn.tools_used.append(call.name)
            turn.tool_context += f'[{call.name}] {output}\n'
            result_blocks.append({'type': 'tool_result', 'tool_call_id': call.id, 'content': output})
        messages.append({'role': 'user', 'content': result_blocks})
    else:
        # Loop guard tripped: ask for a final answer without tools.
        logger.warning('Agent hit MAX_TOOL_ITERATIONS (user=%s ai=%s)', user_id, ai_id)
        result = provider.generate(model=model, system=system, messages=messages,
                                   tools=None, max_tokens=DEFAULT_MAX_TOKENS)
        turn.text = result.text
        turn.total_input_tokens += result.usage.input_tokens
        turn.total_output_tokens += result.usage.output_tokens

    if turn.stop_reason == base.STOP_REFUSAL and not turn.text:
        turn.text = "I'd rather not go there — want to talk about something else?"

    cost = calculate_cost(model, turn.total_input_tokens, turn.total_output_tokens)
    logger.info('Agent turn done: model=%s tools=%s tokens=%s/%s cost=%s',
                model, turn.tools_used, turn.total_input_tokens, turn.total_output_tokens,
                f'${cost:.4f}' if cost is not None else 'n/a')
    return turn
