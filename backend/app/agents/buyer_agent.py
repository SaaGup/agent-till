"""The AI Buyer agent.

Runs an explicit tool-use loop rather than a turnkey SDK runner, because every tool call has
to pass through the circuit breaker and be surfaced to the UI as it happens — the visible tool
trace is the point, not an implementation detail. The loop is provider-agnostic (see llm.py).
"""

import json
import logging
from collections.abc import AsyncIterator

from app.agents.llm import build_llm
from app.agents.mcp_client import mcp_session
from app.agents.prompts import BUYER_SYSTEM_PROMPT
from app.audit.logger import log_action, new_correlation_id
from app.db import SessionLocal
from app.policy.engine import CircuitBreaker, CircuitOpenError
from app.policy.rules import PolicyConfig

log = logging.getLogger(__name__)

# Per-session conversation history. In-memory is deliberate: sessions are anonymous and
# disposable, and nothing here is the system of record — the audit log is.
_HISTORY: dict[str, list[dict]] = {}
MAX_MESSAGE_CHARS = 2000
MAX_HISTORY_MESSAGES = 40


def _result_text(result) -> str:
    parts = [getattr(b, "text", None) for b in result.content]
    return "\n".join(p for p in parts if p) or "{}"


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

    llm = build_llm()
    if llm is None:
        yield {
            "type": "error",
            "message": "No model provider is configured, so the buyer agent can't reason yet.",
        }
        yield {"type": "done"}
        return

    history = _HISTORY.setdefault(session_id, [])
    history.append({"role": "user", "content": user_message[:MAX_MESSAGE_CHARS]})

    try:
        async with mcp_session(session_id, correlation_id) as session:
            listed = await session.list_tools()
            tools = llm.format_tools(listed.tools)

            while True:
                step = llm.step(BUYER_SYSTEM_PROMPT, history, tools)
                history.append(llm.assistant_message(step))

                if step.text.strip():
                    yield {"type": "text", "text": step.text}

                if not step.tool_calls:
                    break

                for call in step.tool_calls:
                    breaker.record_call()
                    yield {"type": "tool_call", "name": call.name, "input": call.arguments}

                    result = await session.call_tool(call.name, call.arguments)
                    payload = _result_text(result)
                    is_error = bool(getattr(result, "is_error", False)) or _looks_like_error(payload)
                    breaker.record_result(is_error=is_error)

                    yield {
                        "type": "tool_result",
                        "name": call.name,
                        "is_error": is_error,
                        "result": payload[:1500],
                    }
                    history.append(llm.tool_result_message(call, payload, is_error))

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

    # Trim oldest turns rather than growing the context (and the bill) without bound.
    if len(history) > MAX_HISTORY_MESSAGES:
        del history[: len(history) - MAX_HISTORY_MESSAGES]

    yield {"type": "done"}


def reset_session(session_id: str) -> None:
    _HISTORY.pop(session_id, None)
