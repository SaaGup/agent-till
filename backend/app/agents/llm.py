"""Provider-agnostic agent LLM layer.

The agent's value is in the policy engine, the audit trail and the MCP tool surface — none of
which should care which vendor answers the prompt. This normalises tool-calling across an
OpenAI-compatible endpoint (Groq, Cerebras, OpenRouter, Gemini's compat endpoint, …) and
Anthropic, so the provider is a config line rather than a rewrite.
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.config import settings

log = logging.getLogger(__name__)

MAX_RATE_LIMIT_RETRIES = 3


def _suggested_retry_delay(message: str) -> float | None:
    match = re.search(r"retryDelay'?: '?(\d+(?:\.\d+)?)s", message)
    return float(match.group(1)) if match else None


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class Step:
    """One assistant turn: some text, and/or some tool calls it wants executed."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: Any = None


class LLM(Protocol):
    def step(self, system: str, messages: list[dict], tools: list[dict]) -> Step: ...
    def assistant_message(self, step: Step) -> dict: ...
    def tool_result_message(self, call: ToolCall, content: str, is_error: bool) -> dict: ...
    def complete(self, system: str, prompt: str, max_tokens: int = 400) -> str: ...


def _tools_openai(mcp_tools: list) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": (t.description or "").strip()[:1024],
                "parameters": t.input_schema,
            },
        }
        for t in mcp_tools
    ]


def _tools_anthropic(mcp_tools: list) -> list[dict]:
    return [
        {
            "name": t.name,
            "description": (t.description or "").strip(),
            "input_schema": t.inputSchema,
        }
        for t in mcp_tools
    ]


class OpenAICompatLLM:
    """Works against any OpenAI-compatible chat-completions endpoint."""

    format_tools = staticmethod(_tools_openai)

    def __init__(self, api_key: str, base_url: str, model: str):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def _create(self, **kwargs):
        """Free tiers throttle aggressively, and a 429 mid-demo would look like a crash.
        Retries the provider's own suggested delay before giving up."""
        from openai import RateLimitError

        delay = 2.0
        for attempt in range(MAX_RATE_LIMIT_RETRIES):
            try:
                return self._client.chat.completions.create(**kwargs)
            except RateLimitError as e:
                if attempt == MAX_RATE_LIMIT_RETRIES - 1:
                    raise
                wait = _suggested_retry_delay(str(e)) or delay
                log.warning("rate limited, retrying", extra={"wait_s": wait, "attempt": attempt})
                time.sleep(min(wait, 30))
                delay *= 2
        raise RuntimeError("unreachable")

    def step(self, system: str, messages: list[dict], tools: list[dict]) -> Step:
        response = self._create(
            model=self._model,
            messages=[{"role": "system", "content": system}, *messages],
            tools=tools or None,
            max_tokens=1500,
        )
        message = response.choices[0].message
        calls = []
        for call in message.tool_calls or []:
            raw_args = call.function.arguments or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                # Smaller open models occasionally emit malformed argument JSON; treating it
                # as an empty call lets the tool layer return a real error the agent can read,
                # rather than crashing the turn.
                log.warning("could not parse tool arguments", extra={"raw": raw_args[:200]})
                args = {}
            calls.append(ToolCall(id=call.id, name=call.function.name, arguments=args))

        return Step(text=message.content or "", tool_calls=calls, raw=message)

    def assistant_message(self, step: Step) -> dict:
        # Echo the provider's own message back rather than rebuilding it from the fields we
        # parsed. Gemini 3.x attaches a thought_signature inside tool_calls[].extra_content and
        # rejects the next turn if it goes missing; rebuilding silently drops any such
        # provider-specific data.
        if step.raw is not None:
            try:
                return step.raw.model_dump(exclude_none=True)
            except AttributeError:
                pass

        msg: dict = {"role": "assistant", "content": step.text or ""}
        if step.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
                }
                for c in step.tool_calls
            ]
        return msg

    def tool_result_message(self, call: ToolCall, content: str, is_error: bool) -> dict:
        return {"role": "tool", "tool_call_id": call.id, "content": content}

    def complete(self, system: str, prompt: str, max_tokens: int = 400) -> str:
        response = self._create(
            model=self._model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""


class AnthropicLLM:
    format_tools = staticmethod(_tools_anthropic)

    def __init__(self, api_key: str, model: str):
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def step(self, system: str, messages: list[dict], tools: list[dict]) -> Step:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1500,
            system=system,
            tools=tools,
            messages=messages,
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        calls = [
            ToolCall(id=b.id, name=b.name, arguments=b.input or {})
            for b in response.content
            if b.type == "tool_use"
        ]
        return Step(text=text, tool_calls=calls, raw=response.content)

    def assistant_message(self, step: Step) -> dict:
        return {"role": "assistant", "content": step.raw}

    def tool_result_message(self, call: ToolCall, content: str, is_error: bool) -> dict:
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": content,
                    "is_error": is_error,
                }
            ],
        }

    def complete(self, system: str, prompt: str, max_tokens: int = 400) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in response.content if b.type == "text")


def build_llm() -> LLM | None:
    """Returns None when no provider is configured, so the app still runs (and the UI says so)
    rather than failing at import time."""
    provider = settings.llm_provider.lower()

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            return None
        return AnthropicLLM(settings.anthropic_api_key, settings.anthropic_model)

    if not settings.llm_api_key:
        return None
    return OpenAICompatLLM(settings.llm_api_key, settings.llm_base_url, settings.llm_model)


def llm_enabled() -> bool:
    return build_llm() is not None
