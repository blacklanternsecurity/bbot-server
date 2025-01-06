from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager

from bbot_server.applets import APP_ROOT


@asynccontextmanager
async def lifespan(app: FastAPI):
    await APP_ROOT.setup()
    yield


app_kwargs = {
    "title": "BBOT Server",
    "description": "A central command center for all your nefarious BBOT activities 🧡",
    "debug": True,
}


app = FastAPI(
    lifespan=lifespan,
    prefix="/v1",
    **app_kwargs,
)
app.include_router(APP_ROOT.router)


@app.get("/", include_in_schema=False)
async def docs_redirect():
    return RedirectResponse(url="docs")


# includes the /v1 prefix
server_app = FastAPI(
    lifespan=lifespan,
    **app_kwargs,
)
server_app.mount("/v1", app)


@server_app.get("/", include_in_schema=False)
async def docs_redirect_2():
    return RedirectResponse(url="/v1/docs")
