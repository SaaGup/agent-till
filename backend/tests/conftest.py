from app.config import settings

# Tests exercise the HTTP API directly and never speak MCP, so binding the MCP port on every
# TestClient is pure contention — several clients in one session fought over it and failed with
# "This portal is not running".
settings.enable_mcp_server = False
