import orjson
import inspect
import logging
import asyncio
import functools
from fastapi import WebSocket
from contextlib import suppress
from fastapi.responses import StreamingResponse
from starlette.websockets import WebSocketDisconnect
import bbot_server.config as bbcfg
from bbot_server.api.mcp import MCP_ENDPOINTS
from bbot_server.utils.misc import smart_encode
from bbot_server.errors import BBOTServerValueError


log = logging.getLogger("bbot_server.applets.routing")

ROUTE_TYPES = {}


def _patch_websocket_signature(original_function, wrapper_function):
    """
    Creates a signature for a websocket wrapper function that includes the websocket parameter
    and all parameters from the original function.

    This is needed because FastAPI requires 'websocket' as a positional argument in the function signature
    """
    original_signature = inspect.signature(original_function)
    wrapper_function.__signature__ = inspect.Signature(
        parameters=[
            inspect.Parameter("websocket", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=WebSocket),
            *[p for p in original_signature.parameters.values()],
        ],
        return_annotation=original_signature.return_annotation,
    )


def fastapi_wrap(function):
    """
    Convenience helper for turning a BBOT Server applet method into a FastAPI-ready function
    """
    route = make_bbotserver_route(function)
    return route.wrapped_function()


def make_bbotserver_route(function, tags=[]):
    """
    Given a BBOTServer applet method, add it to a FastAPI app as a route.

    Args:
        function: The BBOTServer applet method to add to the FastAPI app.
        **fastapi_kwargs: Additional keyword arguments to pass to the FastAPI app. These will override any arguments specified in the @api_endpoint decorator.
    """
    # see if the value has an "_endpoint" attribute
    path = getattr(function, "_endpoint", None)
    # if it's a callable function and it has _endpoint, it's an @api_endpoint

    if path is None:
        raise BBOTServerValueError(f"Function {function.__name__} does not have an _endpoint attribute")

    endpoint_kwargs = dict(getattr(function, "_kwargs", {}))
    endpoint_type = endpoint_kwargs.pop("type", "http")

    try:
        route_class = ROUTE_TYPES[endpoint_type]
    except KeyError:
        raise BBOTServerValueError(f"Invalid endpoint type: {endpoint_type}")

    return route_class(function, tags=tags)


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
        self.orig_function = function
        self.function_signature = inspect.signature(self.orig_function)

        self.function = self.wrapped_function()
        self.default_path = getattr(self.orig_function, "_endpoint", None)

        # these are the kwargs specified in the @api_endpoint decorator
        # they are fastapi kwargs with a few extra ones which we'll pop off here
        self.kwargs = dict(getattr(self.orig_function, "_kwargs", {}))
        self.kwargs.pop("type", None)
        self.response_model = self.kwargs.pop("response_model", None)
        if self.requires_response_model and self.response_model is None:
            raise BBOTServerValueError(
                f"Function {function.__name__}: Must specify a pydantic model used for deserializing {self.endpoint_type} streams"
            )
        self.mcp = self.kwargs.pop("mcp", False)
        if self.mcp:
            MCP_ENDPOINTS[self.function_name] = self.orig_function
        self.tags = tags

    def wrapped_function(self):
        """
        Optionally wrap the function for optimal compatability with fastapi's routing system
        """
        return self.orig_function

    @property
    def function_name(self):
        return self.orig_function.__name__

    def add_to_applet(self, applet):
        """
        Add this BBOT Server route to the given applet's FastAPI router
        """
        self.add_to_router(applet.router)
        self.fastapi_route = applet.router.routes[-1]
        self.path = self.fastapi_route.path
        self.full_path = f"{applet.full_prefix()}{self.fastapi_route.path}"
        applet.route_maps[self.function_name] = self
        self.setup()

    def add_to_router(self, router, **fastapi_kwargs):
        """
        Add this BBOT Server route to the given FastAPI router
        """
        raise NotImplementedError("Subclasses must implement this method")

    def _add_api_route(self, router, path=None, websocket=False, **fastapi_kwargs):
        path, kwargs = self._prepare_fastapi_kwargs(path=path, **fastapi_kwargs)
        if not "operation_id" in kwargs:
            kwargs["operation_id"] = self.function_name
        if not "tags" in kwargs:
            kwargs["tags"] = self.tags
        router.add_api_route(path, self.wrapped_function(), **kwargs)

    def _add_api_websocket_route(self, router, path=None, **fastapi_kwargs):
        path, kwargs = self._prepare_fastapi_kwargs(path=path, **fastapi_kwargs)
        kwargs.pop("summary", None)
        router.add_api_websocket_route(path, self.wrapped_function(), **kwargs)

    def _prepare_fastapi_kwargs(self, **fastapi_kwargs):
        """
        Fills in any necessary missing defaults in the FastAPI kwargs
        """
        kwargs = dict(self.kwargs)
        kwargs.update(fastapi_kwargs)
        path = kwargs.pop("path", None) or self.default_path
        return path, kwargs

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

    def add_to_router(self, router, **fastapi_kwargs):
        self._add_api_route(router, **fastapi_kwargs)

    def setup(self):
        self.response_model = self.fastapi_route.response_model


class HTTPStreamRoute(BaseServerRoute):
    """
    A route for streaming HTTP endpoints
    """

    endpoint_type = "http_stream"
    requires_response_model = True

    def wrapped_function(self):
        """
        Here we convert a python async generator into a StreamingResponse
        """

        # Define a new async function that wraps the original function
        @functools.wraps(self.orig_function)
        async def wrapper(*args, **kwargs):
            generator = self.orig_function(*args, **kwargs)

            try:
                # Trigger execution by getting the first item
                # This is necessary for error handling
                first_item = await anext(generator)
            except StopAsyncIteration:
                # Empty generator is fine
                return StreamingResponse(iter([]))

            async def async_generator():
                yield smart_encode(first_item) + b"\n"
                async for item in generator:
                    yield smart_encode(item) + b"\n"

            return StreamingResponse(async_generator())

        # Set the wrapper's signature to match the original function
        return wrapper

    def add_to_router(self, router, **fastapi_kwargs):
        self._add_api_route(router, **fastapi_kwargs)


class WebsocketRoute(BaseServerRoute):
    """
    A typical websocket route for persistent two-way communication.
    """

    endpoint_type = "websocket"

    def wrapped_function(self):
        @functools.wraps(self.orig_function)
        async def websocket_auth_wrapper(websocket: WebSocket, *args, **kwargs):
            await websocket.accept()
            api_key = websocket.headers.get(bbcfg.API_KEY_NAME, "")
            valid, reason = bbcfg.check_api_key(api_key)
            if valid:
                await self.orig_function(websocket, *args, **kwargs)
            else:
                await websocket.close(code=1008, reason=reason)

        # _patch_websocket_signature(self.function, websocket_auth_wrapper)
        return websocket_auth_wrapper

    def add_to_router(self, router, **fastapi_kwargs):
        self._add_api_websocket_route(router, **fastapi_kwargs)


class WebsocketStreamOutgoingRoute(BaseServerRoute):
    """
    A simplified websocket route for one-way streaming from the server to the client, similar to `tail`.
    """

    endpoint_type = "websocket_stream_outgoing"
    requires_response_model = True

    def wrapped_function(self):
        @functools.wraps(self.orig_function)
        async def websocket_wrapper(websocket: WebSocket, *args, **kwargs):
            """
            Handles opening and closing of the websocket, allowing the user-defined function to be a simple async generator
            """
            try:
                await websocket.accept()
                api_key = websocket.headers.get(bbcfg.API_KEY_NAME, "")
                valid, reason = bbcfg.check_api_key(api_key)
                if not valid:
                    await websocket.close(code=3000, reason=reason)
                agen = self.orig_function(*args, **kwargs)
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
        _patch_websocket_signature(self.orig_function, websocket_wrapper)
        return websocket_wrapper

    def add_to_router(self, router, **fastapi_kwargs):
        self._add_api_websocket_route(router, **fastapi_kwargs)


class WebsocketStreamIncomingRoute(BaseServerRoute):
    """
    A simplified websocket route for one-way streaming from the client to the server, used for ingesting events etc.
    """

    endpoint_type = "websocket_stream_incoming"
    requires_response_model = True

    def __init__(self, function, **kwargs):
        super().__init__(function, **kwargs)
        # we blank out the function signature
        self.function_signature = inspect.Signature(parameters=[], return_annotation=None)

    def wrapped_function(self):
        return self.websocket_wrapper

    async def websocket_wrapper(self, websocket: WebSocket):
        try:
            await websocket.accept()
            api_key = websocket.headers.get(bbcfg.API_KEY_NAME, "")
            valid, reason = bbcfg.check_api_key(api_key)
            if not valid:
                await websocket.close(code=3000, reason=reason)
                return

            async def agen():
                try:
                    while True:
                        message = await websocket.receive_bytes()
                        message = orjson.loads(message)
                        message = self.response_model(**message)
                        yield message
                except WebSocketDisconnect:
                    log.info("WebSocket disconnected by client")
                except asyncio.CancelledError:
                    log.info("Websocket stream incoming cancelled")
                except RuntimeError as e:
                    log.error(f"Unexpected error in websocket stream: {e}")

            await self.orig_function(agen())
        finally:
            with suppress(BaseException):
                await websocket.close()

    def add_to_router(self, router, **fastapi_kwargs):
        self._add_api_websocket_route(router, **fastapi_kwargs)
