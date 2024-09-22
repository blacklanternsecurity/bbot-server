import os
import json
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.responses import RedirectResponse

from bbot_server import BBOT_IO

backend = os.getenv("BBOT_IO_BACKEND", "sqlite")
kwargs = json.loads(os.getenv("BBOT_IO_CONFIG", "{}"))

io = BBOT_IO(backend, **kwargs)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await io.setup()
    yield


app = FastAPI(
    title="BBOT Server",
    description="A feature-rich database + API for your BBOT scan data 🧡",
    lifespan=lifespan,
    debug=True,
    # docs_url=None
)


@app.get("/", include_in_schema=False)
async def docs_redirect():
    return RedirectResponse(url="/docs")


# docs dark theme
# @app.get("/docs", include_in_schema=False)
# async def custom_swagger_ui_html_cdn():
#     from fastapi.openapi.docs import get_swagger_ui_html
#     return get_swagger_ui_html(
#         openapi_url=app.openapi_url,
#         title=f"{app.title} - Swagger UI",
#         # swagger_ui_dark.css CDN link
#         swagger_css_url="https://cdn.jsdelivr.net/gh/Itz-fork/Fastapi-Swagger-UI-Dark/assets/swagger_ui_dark.min.css"
#     )


app.include_router(io.router)
