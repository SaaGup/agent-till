"""Connects the agents to the merchant's MCP tool surface.

The MCP server runs in this same process on loopback, so this is a local round trip — but it
goes over the real protocol, which is what makes the merchant genuinely agent-callable rather
than just internally refactored.
"""

import logging
from contextlib import asynccontextmanager

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.config import settings

log = logging.getLogger(__name__)


def mcp_url() -> str:
    return f"http://127.0.0.1:{settings.mcp_port}/mcp"


@asynccontextmanager
async def mcp_session(session_id: str, correlation_id: str = ""):
    """The shopper's session id rides on the connection, not in the tool arguments, so the
    model cannot choose which session it is spending from.

    The turn's correlation id rides along too, so a failure and the recovery that follows it
    land in the audit trail as one readable chain rather than unrelated rows.
    """
    headers = {"X-Session-Id": session_id}
    if correlation_id:
        headers["X-Correlation-Id"] = correlation_id
    async with httpx2.AsyncClient(headers=headers) as http_client:
        async with streamable_http_client(mcp_url(), http_client=http_client) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
