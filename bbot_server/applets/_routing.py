import orjson
import inspect
from fastapi import WebSocket
from contextlib import suppress
from fastapi.dependencies.utils import get_typed_return_annotation


def api_endpoint(endpoint, **kwargs):
    def decorator(fn):
        fn._kwargs = kwargs
        fn._endpoint = endpoint
        return fn

    return decorator


class BaseServerRoute:
    def __init__(self, function, tags=[]):
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

    async def websocket_wrapper(self, websocket: WebSocket):
        try:
            await websocket.accept()
            agen = self.function()
            async for message in agen:
                message = orjson.dumps(message)
                await websocket.send_bytes(message)
        finally:
            with suppress(Exception):
                await agen.aclose()
            with suppress(Exception):
                await websocket.close()

    def add_to_router(self, router):
        router.add_api_websocket_route(self.endpoint, self.websocket_wrapper)

    def setup(self):
        self.response_model = get_typed_return_annotation(self.function)
