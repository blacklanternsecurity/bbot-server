from fastapi import FastAPI
from fastapi.responses import RedirectResponse


app = FastAPI(
    title="BBOT Server",
    description="A tiny backend for your BBOT scan data 🧡",
    debug=True,
)


@app.get("/", include_in_schema=False)
async def docs_redirect():
    return RedirectResponse(url="/docs")
