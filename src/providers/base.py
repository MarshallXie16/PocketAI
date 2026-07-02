"""Provider-agnostic LLM interface.

Every provider adapter normalizes its SDK's response into ``LLMResult`` so the
agent loop (src/ai/agent.py) never touches provider-specific fields. Keep this
module dependency-free: no SDK imports here.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol

# Normalized stop reasons — adapters map their SDK's vocabulary onto these.
STOP_END_TURN = 'end_turn'      # model finished a normal reply
STOP_TOOL_USE = 'tool_use'      # model wants tool results before continuing
STOP_MAX_TOKENS = 'max_tokens'  # truncated — response may be incomplete
STOP_REFUSAL = 'refusal'        # model declined; surface gracefully, never retry blindly


@dataclass
class ToolCall:
    """One tool invocation requested by the model."""

    id: str            # provider's call id — must be echoed back with the result
    name: str
    args: dict[str, Any]


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class LLMResult:
    """Normalized model response."""

    text: str                                   # concatenated text content ('' if pure tool call)
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = STOP_END_TURN
    usage: Usage = field(default_factory=Usage)
    model: str = ''
    raw: Any = None                             # provider response, for debugging only


class LLMProvider(Protocol):
    """One adapter per provider. ``messages`` uses the normalized shape:

    ``[{"role": "user"|"assistant", "content": str | list[dict]}]``

    where list-content entries are provider-neutral blocks:
    ``{"type": "text", "text": ...}``,
    ``{"type": "tool_use", "id": ..., "name": ..., "args": {...}}`` (assistant),
    ``{"type": "tool_result", "tool_call_id": ..., "content": str}`` (user).
    Adapters translate these to their SDK's wire format.
    """

    def generate(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 2048,
        stream: bool = False,
    ) -> LLMResult:
        ...
