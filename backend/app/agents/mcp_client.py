"""Connects the agents to the merchant's MCP tool surface.

The MCP server runs in this same process on loopback, so this is a local round trip — but it
goes over the real protocol, which is what makes the merchant genuinely agent-callable rather
than just internally refactored.
"""

import logging
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.config import settings

log = logging.getLogger(__name__)


def mcp_url() -> str:
    return f"http://127.0.0.1:{settings.mcp_port}/mcp"


@asynccontextmanager
async def mcp_session():
    async with streamable_http_client(mcp_url()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session
