import logging
from omegaconf import OmegaConf
from fastapi.security import APIKeyHeader
from contextlib import asynccontextmanager
from fastapi.openapi.utils import get_openapi
from fastapi import FastAPI, Security, HTTPException, Depends
from fastapi.responses import RedirectResponse, ORJSONResponse

import bbot_server.config as bbcfg
from bbot_server.errors import BBOTServerError, handle_bbot_server_error

log = logging.getLogger("bbot_server.api.fastapi")

# from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html

app_kwargs = {
    "title": "BBOT Server",
    "description": "A central database for all your BBOT activities 🧡",
    "debug": True,
}

# API key header
api_key_header = APIKeyHeader(name=bbcfg.API_KEY_NAME, auto_error=False)
valid_api_keys = set(bbcfg.BBOT_SERVER_CONFIG.get("api_keys", []))


async def verify_api_key(api_key: str):
    valid, reason = bbcfg.check_api_key(api_key)
    if not valid:
        raise HTTPException(status_code=403, detail=reason)
    return api_key


# Dependency to verify the API key
async def api_key_dependency(api_key: str = Security(api_key_header)):
    await verify_api_key(api_key)
    


def make_app(config=None):
    from bbot_server.api.mcp import make_mcp_server
    from bbot_server.applets import BBOTServerRootApplet

    app_root = BBOTServerRootApplet(config=config)
    app_root._is_main_server = True

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await app_root.setup()
        yield
        await app_root.cleanup()

    app = FastAPI(
        lifespan=lifespan,
        root_path="/v1",
        openapi_tags=app_root.tags_metadata,
        default_response_class=ORJSONResponse,
        dependencies=[Depends(api_key_dependency)],
        **app_kwargs,
    )

    # Customize OpenAPI to better document the authentication
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        # Prepend root_path to all paths in the OpenAPI schema
        root_path = app.root_path or ""
        if root_path and root_path != "/":
            new_paths = {}
            for path, path_item in openapi_schema["paths"].items():
                if not path.startswith(root_path):
                    new_path = root_path + path
                else:
                    new_path = path
                new_paths[new_path] = path_item
            openapi_schema["paths"] = new_paths

        # Add security scheme to OpenAPI schema
        openapi_schema["components"]["securitySchemes"] = {
            "APIKeyHeader": {
                "type": "apiKey",
                "in": "header",
                "name": API_KEY_NAME,
                "description": "API key authentication",
            }
        }

        # Add global security requirement
        openapi_schema["security"] = [{"APIKeyHeader": []}]

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

    app.include_router(app_root.router)

    # add MCP server to the fastapi app
    make_mcp_server(app, app_root.router)

    @app.get("/", include_in_schema=False)
    async def docs_redirect():
        return RedirectResponse(url="docs")

    # Register the exception handler
    app.exception_handler(BBOTServerError)(handle_bbot_server_error)

    # favicon overrides - not working

    # @app.get("/docs", include_in_schema=False)
    # async def custom_swagger_ui_html():
    #     return get_swagger_ui_html(
    #         openapi_url=app.openapi_url,
    #         title=app.title + " - Swagger UI",
    #         swagger_favicon_url="https://www.blacklanternsecurity.com/bbot/Stable/bbot.png"
    #     )

    # @app.get("/redoc", include_in_schema=False)
    # async def custom_redoc_html():
    #     return get_redoc_html(
    #         openapi_url=app.openapi_url,
    #         title=app.title + " - ReDoc",
    #         redoc_favicon_url="https://www.blacklanternsecurity.com/bbot/Stable/bbot.png"
    #     )

    return app, lifespan


def make_server_app(config=None):
    app, lifespan = make_app(config=config)

    # includes the /v1 prefix
    server_app = FastAPI(
        lifespan=lifespan,
        **app_kwargs,
    )

    @server_app.get("/", include_in_schema=False)
    async def docs_redirect():
        return RedirectResponse(url="/v1/docs")

    server_app.mount("/v1", app)

    return server_app
