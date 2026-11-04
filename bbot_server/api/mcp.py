import logging

from bbot_server.config import BBOT_SERVER_CONFIG as bbcfg

MCP_ENDPOINTS = {}

log = logging.getLogger("bbot_server.api.mcp")


def make_mcp_server(fastapi_app, config, mcp_endpoints=None):
    from fastapi_mcp import FastApiMCP

    if mcp_endpoints is None:
        mcp_endpoints = MCP_ENDPOINTS
    log.debug(f"Creating MCP server with endpoints: {','.join(mcp_endpoints)}")
    # forward the server's auth header to the API during tool calls
    # the default of ["authorization"] is not used because bbot-server authenticates with its own header
    mcp = FastApiMCP(fastapi_app, include_operations=list(mcp_endpoints), headers=[bbcfg.auth_header])
    mcp.mount()
