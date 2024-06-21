import os
from fastapi import FastAPI

from .events import EventAPI

app = FastAPI(title="BBOT Server", description="A central database for your BBOT scan data")

io_module = os.getenv("BBOT_IO_MODULE", "sqlite")
event_api = EventAPI(io_module)
app.include_router(event_api.router)
