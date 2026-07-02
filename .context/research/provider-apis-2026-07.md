# Provider API Shapes Brief — Phase-3 AI-core Rewrite

**Date:** 2026-07-01
**Purpose:** Authoritative reference for writing `LLMProvider` protocol adapters (Anthropic, OpenAI, Google google-genai) for a hand-rolled native tool-use loop.
**Method:** Field names/signatures extracted from the *actually installed* SDK source in `./.venv` (authoritative for the pinned versions). Pricing, model IDs, gotchas, and the not-yet-installed `google-genai` SDK verified via official docs (docs.claude.com, developers.openai.com, ai.google.dev). WebFetch + the `claude-api` skill were denied in this session, so Anthropic facts come from installed `anthropic==0.115.1` source + docs.claude.com search.

**Installed SDK versions (`.venv`):**
- `anthropic==0.115.1`
- `openai==2.44.0`
- `google-generativeai==0.8.6` (LEGACY — package name `google.generativeai`, `__version__ = "0.8.6"`; to be REPLACED by `google-genai`, import `from google import genai`, current PyPI `google-genai` ~v1.53.x, NOT yet installed). Legacy also pulls `google-ai-generativelanguage==0.6.15`.

**Model landscape note (July 2026):** The maintainer's requested Claude trio is `claude-opus-4-8`, `claude-sonnet-4-6`, `claude-haiku-4-5` (no Fable). Current top Sonnet is now **Sonnet 5** (`claude-sonnet-4-6` is a prior-gen ID, still callable but superseded — confirm before pinning). Opus 4.8 and Haiku 4.5 are current.

---

## 1. Anthropic (`anthropic==0.115.1`)

### 1.1 Client + non-streaming chat
```python
from anthropic import Anthropic

client = Anthropic()  # reads ANTHROPIC_API_KEY

resp = client.messages.create(
    model="claude-opus-4-8",
    max_tokens=1024,                     # REQUIRED, positional-or-keyword, no default
    system="You are a helpful assistant.",   # top-level; NO "system" role in messages
    messages=[{"role": "user", "content": "Hello"}],
)
# resp.content -> list[ContentBlock]; resp.stop_reason; resp.usage
text = "".join(b.text for b in resp.content if b.type == "text")
```

`messages.create` full signature (from `anthropic/resources/messages/messages.py`), key params:
`max_tokens: int` (required), `messages: Iterable[MessageParam]` (required), `model` (required),
`system: Union[str, Iterable[TextBlockParam]]`, `temperature: float`, `top_k: int`, `top_p: float`,
`thinking: ThinkingConfigParam`, `tools`, `tool_choice`, `stop_sequences`, `stream: bool`,
`service_tier: Literal["auto","standard_only"]`, `metadata`, `stop_sequences`.

### 1.2 Streaming
```python
with client.messages.stream(
    model="claude-opus-4-8", max_tokens=1024,
    messages=[{"role": "user", "content": "Hi"}],
) as stream:
    for text in stream.text_stream:       # convenience: text deltas only
        print(text, end="")
    final = stream.get_final_message()    # full Message with usage + stop_reason
```
Raw SSE event types: `message_start`, `content_block_start`, `content_block_delta`
(`text_delta` / `input_json_delta` for tool args / `thinking_delta`), `content_block_stop`,
`message_delta` (carries `stop_reason` + cumulative `usage`), `message_stop`.
`.messages.stream(...)` (context manager) is preferred over `.create(..., stream=True)`.

### 1.3 Native tool use
**Declare tools** (`ToolParam`): each tool = `{name, description, input_schema}`.
`input_schema` is a JSON Schema object with `type: "object"`, `properties`, `required`.
```python
tools = [{
    "name": "get_weather",
    "description": "Get current weather for a city.",
    "input_schema": {
        "type": "object",
        "properties": {"city": {"type": "string", "description": "City name"}},
        "required": ["city"],
    },
}]
```
**Model returns a tool call** as a content block in `resp.content` with `stop_reason == "tool_use"`.
`ToolUseBlock` fields: `type="tool_use"`, `id: str`, `name: str`, `input: dict`.
```python
for block in resp.content:
    if block.type == "tool_use":
        tool_use_id, name, args = block.id, block.name, block.input
```
**Feed results back** — append the assistant turn (echo `resp.content`), then a new `user`
message containing a `tool_result` block. `ToolResultBlockParam` fields:
`type="tool_result"`, `tool_use_id: str` (REQUIRED, must match the `tool_use.id`),
`content: Union[str, list[block]]`, `is_error: bool` (optional).
```python
messages.append({"role": "assistant", "content": resp.content})
messages.append({"role": "user", "content": [{
    "type": "tool_result",
    "tool_use_id": tool_use_id,
    "content": "72F and sunny",     # or a list of text/image blocks
    # "is_error": True,            # set when the tool raised
}]})
resp = client.messages.create(model=..., max_tokens=..., messages=messages, tools=tools)
```
`tool_choice`: `{"type": "auto"}` (default), `{"type": "any"}` (must call some tool),
`{"type": "tool", "name": "..."}` (force), `{"type": "none"}`.
**Loop terminates** when `stop_reason != "tool_use"` (i.e. `end_turn`, `max_tokens`, `stop_sequence`, `refusal`).

### 1.4 Stop reasons (exact enum, `anthropic/types/stop_reason.py`)
`Literal["end_turn", "max_tokens", "stop_sequence", "tool_use", "pause_turn", "refusal"]`
- `end_turn` — natural completion.
- `max_tokens` — hit `max_tokens`; output truncated.
- `stop_sequence` — matched a `stop_sequences` entry (see `resp.stop_sequence`).
- `tool_use` — model wants a tool run; continue loop.
- `pause_turn` — long-running server-tool turn paused; resume by sending the response back.
- `refusal` — model declined for safety; stop the loop, surface to user.

### 1.5 System prompt & structured content
- System prompt: top-level `system=` param (string OR list of `TextBlockParam`). Passing a
  list lets you mark parts cacheable via `cache_control`.
- Retrieved context (RAG) as a distinct block, NOT string concat: pass user `content` as a list
  of blocks, e.g. a `{"type":"document", ...}` block or a dedicated `{"type":"text","text": context}`
  block plus the question block. `ToolResultBlockParam.content` also accepts a block list
  (text/image/search_result/document) — return structured tool output that way.
- `max_tokens` is REQUIRED on every call.

### 1.6 Hard constraints / gotchas (Opus 4.8 especially)
- **`temperature`, `top_p`, `top_k` are NOT supported on Claude Opus 4.8** — any non-default value
  returns **400**. Omit them entirely for Opus 4.8; guide behavior via prompting. (These remain
  valid on Sonnet/Haiku.)
- **Extended thinking** (`thinking=`): union of three shapes (`anthropic/types/thinking_config_*`):
  - `{"type": "enabled", "budget_tokens": int}` — `budget_tokens` **≥1024 and < max_tokens** (counts toward `max_tokens`). Optional `display: "summarized"|"omitted"`.
  - `{"type": "adaptive"}` — model chooses its own thinking budget (new; optional `display`).
  - `{"type": "disabled"}`.
  - Thinking is **incompatible with `temperature`/`top_k` mods and forced tool use**. With thinking on, `top_p` only valid in `[0.95, 1]`. Cannot combine with `max_tokens: 0` (cache pre-warm) since budget < max_tokens.
- **Streaming required for large `max_tokens`:** the SDK validates non-streaming requests aren't
  expected to exceed a ~10-min timeout and will raise, instructing you to stream. Use `.messages.stream`
  for long/large-output calls. Opus 4.8 supports up to **128k output tokens** (300k via `output-300k-2026-03-24` beta header on Batches).
- `refusal` stop reason → do not retry blindly; treat as terminal.
- Response content blocks can include `thinking`/`redacted_thinking` blocks (see `ContentBlock` union) — filter to `type=="text"` for display, and **echo thinking blocks back unmodified** in multi-turn tool loops when thinking is enabled (needed for signature continuity).

### 1.7 Token / cost fields (`anthropic/types/usage.py`, on `resp.usage`)
`input_tokens: int`, `output_tokens: int` (authoritative billed total),
`cache_creation_input_tokens`, `cache_read_input_tokens`, `cache_creation` (TTL breakdown),
`output_tokens_details` (e.g. reasoning tokens, observability only),
`server_tool_use`, `service_tier: Literal["standard","priority","batch"]`, `inference_geo`.

### 1.8 Pricing (per MTok, USD, standard tier — July 2026)
| Model | Input | Output | Notes |
|-------|-------|--------|-------|
| `claude-opus-4-8` | $5 | $25 | Fast mode $10/$50. Prompt caching up to 90% off; batch 50% off. |
| `claude-sonnet-4-6` (prior-gen Sonnet) | ~$3 | ~$15 | Superseded by **Sonnet 5** ($2/$10 intro thru 2026-08-31, then $3/$15). |
| `claude-haiku-4-5` | $1 | $5 | |

### 1.9 Error taxonomy (`anthropic/_exceptions.py`) — worth catching
Base `APIStatusError` (has `.status_code`, `.request_id`):
- `BadRequestError` 400 — invalid params (e.g. temperature on Opus 4.8). Do NOT retry; fix request.
- `AuthenticationError` 401, `PermissionDeniedError` 403, `NotFoundError` 404, `ConflictError` 409.
- `RequestTooLargeError` 413 — payload too big.
- `UnprocessableEntityError` 422.
- `RateLimitError` 429 — **retry with backoff**; honor `retry-after` header.
- `InternalServerError` 5xx, `ServiceUnavailableError` 503, `DeadlineExceededError` 504.
- `OverloadedError` 529 — Anthropic overloaded; **retry with backoff/jitter**.
Non-status: `APIConnectionError`, `APITimeoutError` (retryable), `APIResponseValidationError`.
The SDK retries `408/409/429/5xx` automatically (default `max_retries=2`); tune via `Anthropic(max_retries=...)`.

---

## 2. OpenAI (`openai==2.44.0`) — Responses API (primary)

The rewrite should target the **Responses API** (`client.responses`), OpenAI's current primary
surface. Chat Completions (`client.chat.completions`) still exists for compatibility.

### 2.1 Client + non-streaming
```python
from openai import OpenAI

client = OpenAI()  # OPENAI_API_KEY

resp = client.responses.create(
    model="gpt-5.2",
    instructions="You are a helpful assistant.",   # system prompt
    input="Hello",                                  # str OR list of input items
    max_output_tokens=1024,
)
text = resp.output_text        # convenience aggregator over output items
```
`responses.create` key params (from `openai/resources/responses/responses.py`):
`input: Union[str, ResponseInputParam]`, `instructions: Optional[str]` (system prompt),
`model`, `max_output_tokens`, `tools`, `tool_choice`, `parallel_tool_calls`,
`reasoning: Reasoning` (e.g. `{"effort": "low|medium|high|xhigh"}`), `text` (structured-output config),
`temperature`, `top_p` (**see gotcha 2.6**), `stream`, `store`, `previous_response_id`,
`conversation`, `service_tier`, `max_tool_calls`, `truncation`.

### 2.2 Streaming
```python
stream = client.responses.create(model="gpt-5.2", input="Hi", stream=True)
for event in stream:            # typed ResponseStreamEvent objects
    if event.type == "response.output_text.delta":
        print(event.delta, end="")
# terminal event: response.completed (carries final Response w/ usage)
```
Event types include `response.created`, `response.output_item.added`,
`response.output_text.delta`, `response.function_call_arguments.delta`,
`response.completed`, `response.failed`, `response.incomplete`.

### 2.3 Native function calling
**Declare** (`FunctionToolParam`) — note tool schema lives at TOP LEVEL (not nested under `function`):
```python
tools = [{
    "type": "function",
    "name": "get_weather",
    "description": "Get current weather for a city.",
    "parameters": {                     # JSON schema, REQUIRED (nullable)
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
        "additionalProperties": False,
    },
    "strict": True,                     # REQUIRED field; default True (strict schema)
}]
```
**Model returns** a `function_call` output item (`ResponseFunctionToolCall`) in `resp.output`:
fields `type="function_call"`, `call_id: str`, `name: str`, `arguments: str` (**JSON string**, must `json.loads`), plus optional `id`, `status`.
```python
import json
for item in resp.output:
    if item.type == "function_call":
        args = json.loads(item.arguments)
        call_id = item.call_id
```
**Feed results back** — append a `function_call_output` input item (`FunctionCallOutput`):
fields `type="function_call_output"`, `call_id: str` (REQUIRED, matches the call), `output: Union[str, list[content]]` (REQUIRED).
```python
new_input = previous_input + [
    item,   # echo the function_call item back
    {"type": "function_call_output", "call_id": call_id, "output": "72F and sunny"},
]
resp = client.responses.create(model="gpt-5.2", input=new_input, tools=tools)
# OR use previous_response_id=resp.id and send only the function_call_output items.
```
`output` may be a string or a list of content items (`input_text`/`input_image`/`input_file`) for structured/multimodal tool output.

### 2.4 Finish / stop signals
Responses API uses `resp.status` (`response_status.py`):
`Literal["completed","failed","in_progress","cancelled","queued","incomplete"]`.
- Presence of a `function_call` item in `resp.output` → run the tool and loop.
- `status == "incomplete"` → check `resp.incomplete_details.reason`
  (`Literal["max_output_tokens","content_filter"]`).
- `status == "failed"` → `resp.error`.
- Loop terminates when `status == "completed"` and no `function_call` items remain.

(Chat Completions equivalent, for reference: `choice.finish_reason ∈
{"stop","length","tool_calls","content_filter","function_call"}`.)

### 2.5 System prompt & structured content
- System prompt = top-level `instructions=`.
- Retrieved context as a distinct block: `input` accepts a list of message items whose `content`
  is a list of typed parts, e.g.
  `{"role":"user","content":[{"type":"input_text","text": rag_context},{"type":"input_text","text": question}]}`
  — pass context as its own `input_text` part rather than concatenating strings. `input_file`/`input_image` parts also supported.
- `max_output_tokens` is optional but recommended for cost control.

### 2.6 Hard constraints / gotchas
- **GPT-5 series are reasoning models: `temperature` and `top_p` are NOT supported** — sending them
  returns `"'temperature' is not supported with this model."` (400). Omit them; use
  `reasoning.effort` (`none`(default)/`low`/`medium`/`high`/`xhigh`) to control depth.
- `arguments` in a function_call is a **JSON string**, not a dict — always `json.loads`.
- Length cutoff surfaces as `status="incomplete"` + `incomplete_details.reason="max_output_tokens"`
  (Responses API) or raises `LengthFinishReasonError` in some helpers (Chat Completions parse path).
- Content filter → `incomplete_details.reason="content_filter"` / `ContentFilterFinishReasonError`.
- `store=True` (default) persists responses server-side for `previous_response_id` chaining; set
  `store=False` for stateless/privacy.

### 2.7 Token / cost fields (`resp.usage`, `response_usage.py`)
`input_tokens: int`, `output_tokens: int`, `total_tokens: int`,
`input_tokens_details.cached_tokens`, `output_tokens_details.reasoning_tokens`.

### 2.8 Embeddings (`client.embeddings.create`, `openai/resources/embeddings.py`)
```python
emb = client.embeddings.create(
    model="text-embedding-3-small",
    input="text to embed",       # str | list[str] | token ids
    dimensions=1536,             # optional; shorten output dims (default 1536; max 1536 for -small)
    encoding_format="float",     # or "base64"
)
vec = emb.data[0].embedding      # list[float]; emb.usage.total_tokens
```
`EmbeddingModel` literal: `text-embedding-ada-002`, `text-embedding-3-small`, `text-embedding-3-large`.
`text-embedding-3-small`: default **1536** dims (reducible via `dimensions`), ~$0.02/MTok.
`text-embedding-3-large`: default 3072 dims.

### 2.9 Transcription / STT (`client.audio.transcriptions.create`) — Phase 4c
```python
with open("audio.mp3", "rb") as f:
    tr = client.audio.transcriptions.create(
        model="gpt-4o-transcribe",     # or "gpt-4o-mini-transcribe", "whisper-1"
        file=f,
    )
text = tr.text
```
`AudioModel` literal: `whisper-1`, `gpt-4o-transcribe`, `gpt-4o-mini-transcribe`,
`gpt-4o-mini-transcribe-2025-12-15`, `gpt-4o-transcribe-diarize`.
Params: `file` (required), `model` (required), `language`, `prompt`, `temperature`,
`response_format` (`json`/`text`/`srt`/`vtt`/`verbose_json`/`diarized_json`),
`timestamp_granularities: ["word","segment"]`, `chunking_strategy`, `stream=True` (SSE deltas).
**Recommendation:** `gpt-4o-transcribe` (lower WER, better multilingual than `whisper-1`);
`whisper-1` only if you need `verbose_json` segment timestamps cheaply.

### 2.10 Error taxonomy (`openai/_exceptions.py`)
Base `APIStatusError` (`.status_code`, `.request_id`, `.body`):
- `BadRequestError` 400 (invalid_request — e.g. temperature on GPT-5). Fix, don't retry.
- `AuthenticationError` 401 (+ `OAuthError`), `PermissionDeniedError` 403, `NotFoundError` 404,
  `ConflictError` 409, `UnprocessableEntityError` 422.
- `RateLimitError` 429 — retry w/ backoff, honor `retry-after`.
- `InternalServerError` 5xx — retry w/ backoff.
Non-status: `APIConnectionError`, `APITimeoutError` (retryable).
Finish-reason exceptions: `LengthFinishReasonError`, `ContentFilterFinishReasonError`.
SDK auto-retries 408/409/429/5xx (default `max_retries=2`); tune `OpenAI(max_retries=...)`.

### 2.11 Chat model equivalents (July 2026)
Pick reasoning models via `reasoning.effort`; there is no separate "flash/pro" axis.
| Tier | Model ID | Input $/MTok | Output $/MTok |
|------|----------|--------------|---------------|
| Pro | `gpt-5.2` (or latest `gpt-5.5`) | $1.75 | $14 | (90% cached-input discount) |
| Flash | `gpt-5-mini` / `gpt-5.2-mini` | ~$0.25 | ~$2 | *verify exact rate on pricing page* |

---

## 3. Google Gemini — `google-genai` (NEW SDK, target) vs `google-generativeai` 0.8.6 (legacy, installed)

### 3.1 NEW SDK: client + generate_content
```python
from google import genai
from google.genai import types

client = genai.Client(api_key="...")     # or Vertex: genai.Client(vertexai=True, project=..., location=...)

resp = client.models.generate_content(
    model="gemini-3-pro-preview",
    contents="Hello",                     # str | list[Content] | list[Part]
    config=types.GenerateContentConfig(
        system_instruction="You are a helpful assistant.",   # text only
        max_output_tokens=1024,
        temperature=0.7,
    ),
)
print(resp.text)                          # convenience aggregator
```
Everything except `model`/`contents` goes inside `config=types.GenerateContentConfig(...)`
(system_instruction, max_output_tokens, temperature, top_p, top_k, tools, tool_config,
thinking_config, safety_settings, response_mime_type/response_schema). Config accepts a dict or the pydantic type.

### 3.2 Streaming
```python
for chunk in client.models.generate_content_stream(
    model="gemini-3-pro-preview", contents="Hi"):
    print(chunk.text, end="")
```

### 3.3 Function calling (manual mode — needed for a hand-rolled loop)
```python
weather_fn = types.FunctionDeclaration(
    name="get_weather",
    description="Get current weather for a city.",
    parameters={   # JSON-schema-like; or types.Schema(...)
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    },
)
tool = types.Tool(function_declarations=[weather_fn])

resp = client.models.generate_content(
    model="gemini-3-pro-preview",
    contents=[types.Content(role="user", parts=[types.Part(text="weather in Paris?")])],
    config=types.GenerateContentConfig(
        tools=[tool],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),  # manual loop
    ),
)
```
**Model returns** function calls — `resp.function_calls` (convenience) or dig into
`resp.candidates[0].content.parts[i].function_call` with fields `.name: str`, `.args: dict`
(already a dict — NOT a JSON string, unlike OpenAI). Finish signal: `candidate.finish_reason`
(`STOP`, `MAX_TOKENS`, `SAFETY`, `RECITATION`, `MALFORMED_FUNCTION_CALL`, etc.).
**Feed results back** — append the model's `Content` (with the `function_call` part), then a new
`Content` with a `function_response` part:
```python
fc = resp.function_calls[0]
contents.append(resp.candidates[0].content)        # echo model turn
contents.append(types.Content(role="user", parts=[
    types.Part.from_function_response(name=fc.name, response={"result": "72F sunny"}),
]))
resp = client.models.generate_content(model=..., contents=contents, config=...)
```
`function_response.response` must be a dict/JSON object. Loop terminates when a candidate has no
`function_call` parts (finish_reason `STOP`). NOTE: if automatic function calling is left enabled
(the new SDK's default for `generate_content`), the SDK runs Python callables for you — disable it
to own the loop.

### 3.4 What changed vs legacy `google-generativeai` 0.8.6 (installed)
Legacy shape (confirmed in `google/generativeai/generative_models.py`, `__version__=="0.8.6"`):
```python
import google.generativeai as genai
genai.configure(api_key=...)
model = genai.GenerativeModel("gemini-1.5-pro",
                              system_instruction=..., tools=..., tool_config=...)
resp = model.generate_content(...)        # config baked into the model object
chat = model.start_chat()                 # automatic function calling only in chat
```
Key differences:
- **Client-centric**: `genai.Client()` replaces module-level `genai.configure()` + per-model
  `GenerativeModel(...)`. Calls go through `client.models.generate_content(...)` (stateless) —
  system_instruction/tools move from the model constructor into `config=`.
- **Unified library** for Gemini Developer API *and* Vertex AI (single SDK; `vertexai=True` flag).
- **Automatic function calling** is now the default in `generate_content` (legacy: only in `start_chat`);
  disable via `AutomaticFunctionCallingConfig(disable=True)` for manual loops.
- All request/response objects are pydantic types under `google.genai.types`.
- `google-generativeai` is deprecated; migrate imports `import google.generativeai as genai` →
  `from google import genai` and rework model/config plumbing.

### 3.5 Current Gemini model IDs & pricing (chat product, July 2026)
All Gemini 3 tiers are in *preview*. For a chat product:
| Tier | Model ID | Input $/MTok | Output $/MTok |
|------|----------|--------------|---------------|
| Flash (default) | `gemini-3-flash-preview` | $0.125 (text/img/video), $0.25 (audio) | $0.75 |
| Flash (newer) | `gemini-3.5-flash` | $1.50 | $9.00 (incl. thinking) |
| Flash-Lite (cheap) | `gemini-3.1-flash-lite` | (lowest tier) | |
| Pro | `gemini-3-pro-preview` / `gemini-3.1-pro-preview` | *verify on pricing page* | *verify* |
Gemini 3 Flash is <¼ the cost of Gemini 3 Pro.

### 3.6 Gemini TTS (`gemini-3.1-flash-tts-preview`)
Audio-output model via the same `generate_content` surface with `response_modalities=["AUDIO"]`.
```python
resp = client.models.generate_content(
    model="gemini-3.1-flash-tts-preview",
    contents="[cheerful] Hello there!",     # inline audio tags control expression
    config=types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore"),
            ),
        ),
    ),
)
audio_bytes = resp.candidates[0].content.parts[0].inline_data.data   # PCM audio
```
- **30 prebuilt voices**, **70+ languages/regional variants**.
- **200+ audio tags** for expressive control, e.g. `[excitement]`, `[whispers]`, `[laughs]`,
  `[determination]`; pacing tags `[slow]`/`[fast]`, `[short pause]`/`[long pause]`.
- Streaming supported via `streamGenerateContent` / `generate_content_stream`.
(Exact `types.SpeechConfig` nesting — verify field names against google-genai when installed.)

---

## 4. Comparison Table

| Aspect | Anthropic | OpenAI (Responses) | Google (google-genai) |
|--------|-----------|--------------------|-----------------------|
| Client | `Anthropic()` | `OpenAI()` | `genai.Client()` |
| Call | `client.messages.create` | `client.responses.create` | `client.models.generate_content` |
| System prompt | top-level `system=` (str/blocks) | top-level `instructions=` | `config.system_instruction` (text only) |
| Max tokens param | `max_tokens` (**required**) | `max_output_tokens` (optional) | `config.max_output_tokens` |
| Tool declaration | `{name, description, input_schema}` (schema top-level) | `{type:"function", name, description, parameters, strict}` (top-level) | `types.Tool(function_declarations=[FunctionDeclaration(name, description, parameters)])` |
| Tool-call in response | content block `type="tool_use"` → `.id`, `.name`, `.input`(dict) | output item `type="function_call"` → `.call_id`, `.name`, `.arguments`(**JSON str**) | `resp.function_calls[i]` → `.name`, `.args`(dict) |
| Tool-result feedback | user msg block `type="tool_result"`, `tool_use_id`, `content`, `is_error` | input item `type="function_call_output"`, `call_id`, `output` | `Content(role="user", parts=[Part.from_function_response(name, response=dict)])` |
| ID linking field | `tool_use_id` == `tool_use.id` | `call_id` == `function_call.call_id` | matched by function `name` (no id) |
| Loop-continue signal | `stop_reason == "tool_use"` | `function_call` item present | candidate has `function_call` part |
| Terminal signals | `end_turn`/`max_tokens`/`stop_sequence`/`refusal`/`pause_turn` | `status`: completed/incomplete/failed (+`incomplete_details.reason`) | `finish_reason`: STOP/MAX_TOKENS/SAFETY/… |
| Streaming | `client.messages.stream(...)` ctx mgr | `create(..., stream=True)` typed events | `generate_content_stream(...)` |
| Args encoding | dict | JSON string | dict |
| Usage fields | `input_tokens`/`output_tokens`(+cache) | `input_tokens`/`output_tokens`/`total_tokens` | `usage_metadata.prompt/candidates/total_token_count` |

---

## 5. Design implications for the `LLMProvider` protocol

**Protocol surface (suggested):**
```python
class LLMProvider(Protocol):
    def complete(self, *, model, system, messages, tools=None, tool_choice=None,
                 max_tokens, temperature=None, stream=False, **kw) -> LLMResult: ...
    def stream(self, ...) -> Iterator[LLMDelta]: ...
    def embed(self, *, model, inputs, dimensions=None) -> list[list[float]]: ...   # OpenAI-only initially
```

**Normalized `LLMResult` fields (adapter output):**
- `text: str` — concatenated assistant text.
- `tool_calls: list[ToolCall]` where `ToolCall = {id: str, name: str, args: dict}`.
  Normalize: Anthropic `tool_use.id`/`.input`; OpenAI `call_id` + `json.loads(arguments)`; Gemini
  synthesize an `id` from `name`+index (Gemini has no native call id — the adapter must generate/track one
  and drop it when echoing `function_response`).
- `stop_reason: Literal["end_turn","tool_use","max_tokens","stop_sequence","refusal","content_filter","error"]`
  — normalized enum mapping:
  - Anthropic: pass-through (`end_turn`/`tool_use`/`max_tokens`/`stop_sequence`/`refusal`; map `pause_turn`→`tool_use`).
  - OpenAI: `function_call` present→`tool_use`; `completed`→`end_turn`; `incomplete_details.reason` max_output_tokens→`max_tokens`, content_filter→`content_filter`; `failed`→`error`.
  - Gemini: `STOP`→`end_turn` (or `tool_use` if function_call part present), `MAX_TOKENS`→`max_tokens`, `SAFETY`/`RECITATION`→`content_filter`, `MALFORMED_FUNCTION_CALL`→`error`.
- `usage: {input_tokens, output_tokens, cached_input_tokens?, reasoning_tokens?}` — normalize:
  Anthropic `input_tokens`/`output_tokens`/`cache_read_input_tokens`/`output_tokens_details`;
  OpenAI `input_tokens`/`output_tokens`/`input_tokens_details.cached_tokens`/`output_tokens_details.reasoning_tokens`;
  Gemini `usage_metadata.*`.
- `cost_usd: float` — computed from a per-model price table (§1.8/2.11/3.5) using normalized usage;
  account for cached-input discounts separately.
- `raw` — keep the provider-native response for debugging.

**Tool loop (provider-agnostic):**
1. Send messages + tools.
2. If `stop_reason == "tool_use"` (normalized): run each `ToolCall`, collect results, append the
   assistant turn + tool-result turn *in each provider's native shape*, resend. Else terminate.
3. Cap iterations (e.g. `max_tool_calls`) to prevent runaway loops.

**Per-provider adapter must-handle quirks:**
- **Opus 4.8**: never send `temperature`/`top_p`/`top_k` (400). Make sampling params provider-conditional.
- **GPT-5 series**: never send `temperature`/`top_p` (400); expose `reasoning.effort` instead.
- Provider-specific ID linking: preserve `tool_use_id`/`call_id`; synthesize for Gemini.
- Args parsing: `json.loads` only for OpenAI; Anthropic/Gemini give dicts.
- System prompt: all three take a dedicated slot — never fold into messages/contents.
- RAG context: pass as a distinct content block/part, not string concat, for all three.
- `max_tokens` required for Anthropic → adapter must always supply a default.
- Large output / long calls → force streaming for Anthropic; watch `incomplete`/`MAX_TOKENS`.
- Unify retry: catch 429 + 5xx (+ Anthropic 529 Overloaded) with exponential backoff + jitter;
  do not retry 400/401/403/404/422.

---

## 6. Sources
- Installed SDK source (authoritative for pinned versions): `./.venv/.../anthropic/` (0.115.1),
  `./.venv/.../openai/` (2.44.0), `./.venv/.../google/generativeai/` (0.8.6, legacy).
- Anthropic docs: https://docs.claude.com/en/api/messages , /en/api/errors ,
  /en/docs/build-with-claude/extended-thinking , /en/docs/build-with-claude/streaming ,
  /en/api/handling-stop-reasons , https://docs.claude.com/en/docs/about-claude/pricing
- Anthropic model announcements: https://www.anthropic.com/news/claude-opus-4-8 ,
  https://www.anthropic.com/news/claude-haiku-4-5 , https://www.anthropic.com/news/claude-sonnet-5
- OpenAI docs: https://developers.openai.com/api/docs/pricing ,
  https://developers.openai.com/api/docs/models/gpt-5.2 ,
  https://developers.openai.com/api/docs/models/text-embedding-3-small ,
  https://developers.openai.com/api/docs/models/gpt-4o-transcribe ,
  https://platform.openai.com/docs/api-reference/responses
- Google GenAI SDK: https://github.com/googleapis/python-genai ,
  https://googleapis.github.io/python-genai/ ,
  https://ai.google.dev/gemini-api/docs/migrate ,
  https://ai.google.dev/api/generate-content
- Gemini models/pricing/TTS: https://ai.google.dev/gemini-api/docs/models ,
  https://ai.google.dev/gemini-api/docs/pricing ,
  https://ai.google.dev/gemini-api/docs/models/gemini-3-flash-preview ,
  https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-tts-preview ,
  https://ai.google.dev/gemini-api/docs/speech-generation

**Verify-before-pinning (couldn't fully confirm this session):** exact `claude-sonnet-4-6` current
pricing/status (Sonnet 5 likely supersedes); exact `gpt-5-mini` and `gemini-3-pro-preview` per-MTok
rates; precise `types.SpeechConfig` field nesting in installed google-genai.
