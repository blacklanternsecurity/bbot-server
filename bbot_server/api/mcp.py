import logging
from fastapi_mcp import FastApiMCP

MCP_ENDPOINTS = {}

log = logging.getLogger("bbot_server.api.mcp")


def make_mcp_server(fastapi_app, config, mcp_endpoints=None):
    if mcp_endpoints is None:
        mcp_endpoints = MCP_ENDPOINTS
    log.debug(f"Creating MCP server with endpoints: {','.join(mcp_endpoints)}")
    mcp = FastApiMCP(fastapi_app, include_operations=list(mcp_endpoints))
    mcp.mount()
