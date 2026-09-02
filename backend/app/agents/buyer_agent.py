"""The AI Buyer agent.

Runs an explicit tool-use loop rather than the SDK's turnkey runner, because every tool call
has to pass through the circuit breaker and be surfaced to the UI as it happens — the visible
tool trace is the point, not an implementation detail.
"""

import json
import logging
from collections.abc import AsyncIterator

import anthropic

from app.agents.mcp_client import mcp_tools
from app.agents.prompts import BUYER_SYSTEM_PROMPT
from app.audit.logger import log_action, new_correlation_id
from app.config import settings
from app.db import SessionLocal
from app.policy.engine import CircuitBreaker, CircuitOpenError
from app.policy.rules import PolicyConfig

log = logging.getLogger(__name__)

# Per-session conversation history. In-memory is deliberate: sessions are anonymous and
# disposable, and nothing here is the system of record — the audit log is.
_HISTORY: dict[str, list[dict]] = {}
MAX_MESSAGE_CHARS = 2000


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _to_anthropic_tools(mcp_tool_list) -> list[dict]:
    return [
        {
            "name": t.name,
            "description": (t.description or "").strip(),
            "input_schema": t.inputSchema,
        }
        for t in mcp_tool_list
    ]


def _result_text(result) -> str:
    parts = []
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts) if parts else "{}"


def _looks_like_error(payload: str) -> bool:
    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        return False
    return isinstance(data, dict) and "error" in data


async def run_buyer_turn(session_id: str, user_message: str) -> AsyncIterator[dict]:
    """Yields UI events: {type: text|tool_call|tool_result|error|circuit_open|done}."""
    cfg = PolicyConfig.from_settings()
    breaker = CircuitBreaker(cfg)
    correlation_id = new_correlation_id()

    if not settings.anthropic_api_key:
        yield {
            "type": "error",
            "message": "No Anthropic API key configured, so the buyer agent can't reason yet.",
        }
        yield {"type": "done"}
        return

    user_message = user_message[:MAX_MESSAGE_CHARS]
    history = _HISTORY.setdefault(session_id, [])
    history.append({"role": "user", "content": user_message})

    client = _client()

    try:
        async with mcp_tools() as (mcp_session, _sdk_tools):
            listed = await mcp_session.list_tools()
            tools = _to_anthropic_tools(listed.tools)

            while True:
                response = client.messages.create(
                    model=settings.anthropic_model,
                    max_tokens=2048,
                    system=BUYER_SYSTEM_PROMPT,
                    tools=tools,
                    messages=history,
                )
                history.append({"role": "assistant", "content": response.content})

                for block in response.content:
                    if block.type == "text" and block.text.strip():
                        yield {"type": "text", "text": block.text}

                if response.stop_reason != "tool_use":
                    break

                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    breaker.record_call()
                    yield {"type": "tool_call", "name": block.name, "input": block.input}

                    result = await mcp_session.call_tool(block.name, block.input or {})
                    payload = _result_text(result)
                    is_error = bool(getattr(result, "isError", False)) or _looks_like_error(payload)
                    breaker.record_result(is_error=is_error)

                    yield {
                        "type": "tool_result",
                        "name": block.name,
                        "is_error": is_error,
                        "result": payload[:1500],
                    }
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": payload,
                            "is_error": is_error,
                        }
                    )

                history.append({"role": "user", "content": tool_results})

    except CircuitOpenError as e:
        with SessionLocal() as db:
            log_action(
                db,
                session_id=session_id,
                actor="ai_buyer_agent",
                action_type="circuit_breaker_tripped",
                correlation_id=correlation_id,
                decision="blocked",
                explanation=f"Agent halted by circuit breaker: {e.reason}",
                policy=cfg,
            )
        yield {"type": "circuit_open", "message": e.reason}
        yield {
            "type": "text",
            "text": (
                "I've paused here rather than keep going — something isn't working the way I "
                "expected, and a human should take a look before I try anything else."
            ),
        }
    except Exception:
        log.exception("buyer agent turn failed")
        yield {"type": "error", "message": "The assistant hit an unexpected problem."}

    yield {"type": "done"}


def reset_session(session_id: str) -> None:
    _HISTORY.pop(session_id, None)
