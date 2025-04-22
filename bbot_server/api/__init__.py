from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from fastapi.responses import RedirectResponse, ORJSONResponse

from bbot_server.errors import BBOTServerError

# from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html

app_kwargs = {
    "title": "BBOT Server",
    "description": "A central database for all your BBOT activities 🧡",
    "debug": True,
}


def make_app(config=None):
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
        prefix="/v1",
        openapi_tags=app_root.tags_metadata,
        default_response_class=ORJSONResponse,
        **app_kwargs,
    )
    app.include_router(app_root.router)

    @app.get("/", include_in_schema=False)
    async def docs_redirect():
        return RedirectResponse(url="docs")

    @app.exception_handler(BBOTServerError)
    async def exception_handler(request: Request, exc: Exception):
        status_code = exc.http_status_code
        error_message = str(exc)
        message = error_message if error_message else exc.default_message
        return ORJSONResponse(
            status_code=status_code,
            content={"error": message, "detail": getattr(exc, "detail", {})},
        )

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
