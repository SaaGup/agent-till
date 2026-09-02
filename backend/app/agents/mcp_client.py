"""Connects the agents to the merchant's MCP tool surface.

The MCP server runs in this same process on loopback, so this is a local round trip — but it
goes over the real protocol, which is what makes the merchant genuinely agent-callable rather
than just internally refactored.
"""

import logging
from contextlib import asynccontextmanager

from anthropic.lib.tools.mcp import async_mcp_tool
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.config import settings

log = logging.getLogger(__name__)


def mcp_url() -> str:
    return f"http://127.0.0.1:{settings.mcp_port}/mcp"


@asynccontextmanager
async def mcp_tools():
    """Yields (session, sdk_tools) ready to hand to the Anthropic tool runner."""
    async with streamable_http_client(mcp_url()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            tools = [async_mcp_tool(t, session) for t in listed.tools]
            log.info("mcp tools loaded", extra={"tool_count": len(tools)})
            yield session, tools
