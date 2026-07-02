"""Shared AI provider clients.

Clients are constructed lazily on first use: constructing them at import
time made the whole app unimportable when an API key was absent (tests,
fresh checkouts, CI). Call sites keep using `openai_client.<attr>` /
`anthropic_client.<attr>` unchanged.
"""

import os

from dotenv import load_dotenv

load_dotenv()


class _LazyClient:
    """Defers client construction until the first attribute access."""

    def __init__(self, factory):
        self._factory = factory
        self._client = None

    def __getattr__(self, item):
        if self._client is None:
            self._client = self._factory()
        return getattr(self._client, item)


def _make_openai():
    from openai import OpenAI
    return OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))


def _make_anthropic():
    import anthropic
    return anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))


openai_client = _LazyClient(_make_openai)
anthropic_client = _LazyClient(_make_anthropic)

# Gemini (legacy google-generativeai SDK — replaced in Phase 3). Importing is
# key-free; configure only when a key is present (None breaks later calls).
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

if os.environ.get('GEMINI_API_KEY'):
    genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))
