import orjson
import inspect
import logging
import asyncio
import functools
from fastapi import WebSocket
from contextlib import suppress
from fastapi.responses import StreamingResponse
from starlette.websockets import WebSocketDisconnect

from bbot_server.utils.misc import smart_encode

log = logging.getLogger("bbot_server.applets.routing")


ROUTE_TYPES = {}


def _patch_websocket_signature(original_function, wrapper_function):
    """
    Creates a signature for a websocket wrapper function that includes the websocket parameter
    and all parameters from the original function.

    This is needed because FastAPI requires 'websocket' as a positional argument in the function signature
    """
    wrapper_function.__signature__ = inspect.Signature(
        parameters=[
            inspect.Parameter("websocket", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=WebSocket),
            *[p for p in inspect.signature(original_function).parameters.values()],
        ],
        return_annotation=inspect.signature(original_function).return_annotation,
    )


class ServerRouteMeta(type):
    """Metaclass for registering BaseServerRoute subclasses"""

    def __new__(cls, name, bases, attrs):
        global ROUTE_TYPES
        new_class = super().__new__(cls, name, bases, attrs)
        # Only register classes that inherit from BaseServerRoute but aren't BaseServerRoute itself
        if bases and BaseServerRoute in bases:
            ROUTE_TYPES[new_class.endpoint_type] = new_class
        return new_class


class BaseServerRoute(metaclass=ServerRouteMeta):
    endpoint_type = None
    requires_response_model = False

    def __init__(self, function, tags=[]):
        self.log = logging.getLogger(f"bbot_server.routing.{self.__class__.__name__.lower()}")
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

    @classmethod
    def get_route_class(cls, endpoint_type):
        """Get a route class by its endpoint_type"""
        return cls.__class__.routes.get(endpoint_type)


class HTTPRoute(BaseServerRoute):
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


class HTTPStreamRoute(BaseServerRoute):
    """
    A route for streaming HTTP endpoints
    """

    endpoint_type = "http_stream"
    requires_response_model = True

    def __init__(self, function, response_model, tags=[]):
        super().__init__(function, tags)
        self.kwargs["tags"] = self.tags
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
                    item = smart_encode(item) + b"\n"
                    yield item

            # Return a StreamingResponse
            return StreamingResponse(async_generator())

        # Set the wrapper's signature to match the original function
        wrapper.__signature__ = sig

        router.add_api_route(self.endpoint, wrapper, **self.kwargs)


class WebsocketRoute(BaseServerRoute):
    """
    A typical websocket route for persistent two-way communication.
    """

    endpoint_type = "websocket"

    def add_to_router(self, router):
        router.add_api_websocket_route(self.endpoint, self.function, **self.kwargs)


class WebsocketStreamOutgoingRoute(BaseServerRoute):
    """
    A simplified websocket route for one-way streaming from the server to the client, similar to `tail`.
    """

    endpoint_type = "websocket_stream_outgoing"
    requires_response_model = True

    def __init__(self, function, response_model, tags=[]):
        super().__init__(function, tags)
        self.response_model = response_model

    def add_to_router(self, router):
        @functools.wraps(self.function)
        async def websocket_wrapper(websocket: WebSocket, *args, **kwargs):
            """
            Handles opening and closing of the websocket, allowing the user-defined function to be a simple async generator
            """
            try:
                await websocket.accept()
                agen = self.function(*args, **kwargs)
                async for message in agen:
                    message = smart_encode(message)
                    await websocket.send_bytes(message)
            except asyncio.CancelledError:
                log.info("Outgoing websocket stream cancelled")
            except WebSocketDisconnect:
                log.info("Outgoing websocket stream disconnected")
            finally:
                with suppress(BaseException):
                    await websocket.close()
                with suppress(BaseException):
                    await agen.aclose()

        # Use the helper function to set the signature
        _patch_websocket_signature(self.function, websocket_wrapper)

        router.add_api_websocket_route(self.endpoint, websocket_wrapper)


class WebsocketStreamIncomingRoute(BaseServerRoute):
    """
    A simplified websocket route for one-way streaming from the client to the server, used for ingesting events etc.
    """

    endpoint_type = "websocket_stream_incoming"
    requires_response_model = True

    def __init__(self, function, response_model, tags=[]):
        super().__init__(function, tags)
        self.response_model = response_model
        self.original_function = function
        self.function = self.websocket_wrapper

    async def websocket_wrapper(self, websocket: WebSocket):
        try:
            await websocket.accept()

            async def agen():
                try:
                    async for message in websocket:
                        message = orjson.loads(message)
                        message = self.response_model(**message)
                        yield message
                except asyncio.CancelledError:
                    log.info("Websocket stream incoming cancelled")
                except RuntimeError as e:
                    log.error(f"Unexpected error in websocket stream: {e}")

            await self.original_function(agen())
        finally:
            with suppress(BaseException):
                await websocket.close()

    def add_to_router(self, router):
        router.add_api_websocket_route(self.endpoint, self.websocket_wrapper)
