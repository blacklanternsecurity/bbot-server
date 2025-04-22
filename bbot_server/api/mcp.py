import logging
from fastapi_mcp import FastApiMCP

MCP_ENDPOINTS = {}

log = logging.getLogger("bbot_server.api.mcp")

logging.getLogger().setLevel(logging.DEBUG)


def make_mcp_server(fastapi_app, config):
    log.critical(f"Creating MCP server with {MCP_ENDPOINTS}")
    mcp = FastApiMCP(fastapi_app, include_operations=list(MCP_ENDPOINTS))
    mcp.mount()
