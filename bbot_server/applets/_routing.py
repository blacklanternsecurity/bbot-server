import orjson
import inspect
import logging
from fastapi import WebSocket
from pydantic import BaseModel
from contextlib import suppress


class BaseServerRoute:
    def __init__(self, function, tags=[]):
        self.log = logging.getLogger(f"bbot.server.routing.{self.__class__.__name__.lower()}")
        self.function = function
        self.endpoint = getattr(function, "_endpoint", None)
        self.function_signature = inspect.signature(function)
        self.kwargs = dict(getattr(function, "_kwargs", {}))
        self.endpoint_type = self.kwargs.pop("type", "http")
        self.tags = tags

    def add_to_applet(self, applet):
        self.add_to_router(applet.router)
        self.fastapi_route = applet.router.routes[-1]
        self.path = self.fastapi_route.path
        self.full_path = f"{applet.full_prefix()}{self.fastapi_route.path}"
        function_name = self.function.__name__
        applet.route_maps[function_name] = self
        self.setup()

    def setup(self):
        pass


class BBOTServerRoute(BaseServerRoute):
    """
    A route for HTTP endpoints
    """

    def __init__(self, function, tags=[]):
        super().__init__(function, tags)
        self.kwargs["tags"] = self.tags

    def add_to_router(self, router):
        router.add_api_route(self.endpoint, self.function, **self.kwargs)

    def setup(self):
        self.response_model = self.fastapi_route.response_model


class WebSocketServerRoute(BaseServerRoute):
    """
    A route for WebSocket endpoints
    """

    def __init__(self, function, tags=[], response_model=None):
        super().__init__(function, tags)
        self.response_model = response_model

    async def websocket_wrapper(self, websocket: WebSocket):
        try:
            await websocket.accept()
            agen = self.function()
            async for message in agen:
                # handle both python and pydantic objects
                if isinstance(message, BaseModel):
                    message = message.model_dump_json().encode()
                else:
                    message = orjson.dumps(message)
                await websocket.send_bytes(message)
        finally:
            with suppress(BaseException):
                await websocket.close()
            with suppress(BaseException):
                await agen.aclose()

    def add_to_router(self, router):
        router.add_api_websocket_route(self.endpoint, self.websocket_wrapper)
