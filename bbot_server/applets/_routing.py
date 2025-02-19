import orjson
import inspect
import logging
from fastapi import WebSocket
from pydantic import BaseModel
from contextlib import suppress
from fastapi.responses import StreamingResponse


log = logging.getLogger("bbot_server.applets.routing")


def smart_encode(obj):
    # handle both python and pydantic objects, as well as strings
    if isinstance(obj, BaseModel):
        return obj.model_dump_json().encode()
    elif isinstance(obj, str):
        return obj.encode()
    elif isinstance(obj, bytes):
        return obj
    else:
        return orjson.dumps(obj)


class BaseServerRoute:
    endpoint_type = None

    def __init__(self, function, tags=[]):
        self.log = logging.getLogger(f"bbot.server.routing.{self.__class__.__name__.lower()}")
        self.function = function
        self.endpoint = getattr(function, "_endpoint", None)
        self.function_signature = inspect.signature(function)
        self.kwargs = dict(getattr(function, "_kwargs", {}))
        self.kwargs.pop("type", "")
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

    endpoint_type = "http"

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

    endpoint_type = "websocket"

    def __init__(self, function, response_model, tags=[]):
        super().__init__(function, tags)
        self.response_model = response_model

    async def websocket_wrapper(self, websocket: WebSocket):
        try:
            await websocket.accept()
            agen = self.function()
            async for message in agen:
                message = smart_encode(message)
                await websocket.send_bytes(message)
        finally:
            with suppress(BaseException):
                await websocket.close()
            with suppress(BaseException):
                await agen.aclose()

    def add_to_router(self, router):
        router.add_api_websocket_route(self.endpoint, self.websocket_wrapper)


class StreamingServerRoute(BBOTServerRoute):
    """
    A route for streaming HTTP endpoints
    """

    endpoint_type = "stream"

    def __init__(self, function, response_model, tags=[]):
        super().__init__(function, tags)
        self.response_model = response_model

    def add_to_router(self, router):
        """
        Here we convert a python async generator into a StreamingResponse
        """

        # Get the function signature
        sig = inspect.signature(self.function)

        # Define a new async function that wraps the original function
        async def wrapper(*args, **kwargs):
            # Call the original async generator function
            async def async_generator():
                async for item in self.function(*args, **kwargs):
                    item = smart_encode(item)
                    yield item

            # Return a StreamingResponse
            return StreamingResponse(async_generator())

        # Set the wrapper's signature to match the original function
        wrapper.__signature__ = sig

        router.add_api_route(self.endpoint, wrapper, **self.kwargs)
