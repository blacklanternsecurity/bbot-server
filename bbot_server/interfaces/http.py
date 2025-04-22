import httpx
import string
import orjson
import asyncio
from functools import partial
from websockets import connect
from contextlib import suppress
from typing import AsyncGenerator
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode, quote


# for converting pydantic objects into raw JSON
from fastapi.encoders import jsonable_encoder

# for converting raw JSON into pydantic objects
from pydantic import TypeAdapter

from bbot_server.interfaces.base import BaseInterface
from bbot_server.utils.async_utils import async_to_sync_class
from bbot_server.errors import HTTP_STATUS_MAPPINGS, BBOTServerError

import logging

log = logging.getLogger(__name__)


@async_to_sync_class
class http(BaseInterface):
    """
    The HTTP interface presents an identical interface to BBOT server, but forwards all function calls as HTTP requests to a remote URL

    This lets us to write the same code for both local and remote
    """

    interface_type = "http"

    _url_safe_chars = string.ascii_letters + string.digits + "-_.~"

    def __init__(self, **kwargs):
        url = kwargs.pop("url", None)
        super().__init__(**kwargs)
        if url is None:
            if not "url" in self.config:
                raise ValueError("When using the HTTP interface, url is required in the config")
            url = self.config["url"]
        self.base_url = url.strip("/")
        self.client = httpx.AsyncClient()

    async def _http_request(self, _url, _route, *args, **kwargs):
        """
        Builds and issues a web request to the bbot server REST API

        Uses the API route to figure out the format etc.
        """
        method, _url, kwargs = self._prepare_api_request(_url, _route, *args, **kwargs)
        body = self._prepare_http_body(method, kwargs)

        try:
            response = await self.client.request(url=_url, method=method, json=body)
        except Exception as e:
            raise BBOTServerError(f"Error making {method} request -> {_url}: {e}") from e

        try:
            response_json = response.json()
        except Exception as e:
            self.log.debug(f"Error decoding response json for {response}: {e} - {getattr(response, 'text', '')}")
            raise BBOTServerError(f"Error decoding response JSON for {response}: {e}") from e

        if not response.is_success:
            # detect errors
            if isinstance(response_json, dict) and "error" in response_json:
                error_class = HTTP_STATUS_MAPPINGS.get(response.status_code, BBOTServerError)
                raise error_class(response_json["error"], detail=response_json.get("detail", {}))

            raise BBOTServerError(f"Error making {method} request -> {_url}: {response.status_code} {response.text}")

        # if our function doesn't have a return type, return the raw JSON
        if _route.response_model is None:
            return response_json

        # otherwise, convert into format matching the return type of the function
        try:
            return TypeAdapter(_route.response_model).validate_python(response_json)
        except Exception as e:
            raise BBOTServerError(
                f"Error validating response json for {method}->{_url}: response: {response_json}: {e}"
            ) from e

    async def _http_stream(self, _url, _route, *args, **kwargs):
        """
        Similar to _request(), but instead of returning a single object, returns an async generator that yields objects
        """
        method, _url, kwargs = self._prepare_api_request(_url, _route, *args, **kwargs)
        body = self._prepare_http_body(method, kwargs)
        buffer = b""
        MAX_BUFFER_SIZE = 10 * 1024 * 1024  # 10 MB max buffer size

        try:
            async with self.client.stream(method=method, url=_url, json=body) as response:
                async for chunk in response.aiter_bytes():
                    buffer += chunk

                    # Check if buffer exceeds maximum size
                    if len(buffer) > MAX_BUFFER_SIZE:
                        raise BBOTServerError(
                            f"Buffer exceeded maximum size of {MAX_BUFFER_SIZE} bytes. Possible malformed JSON stream."
                        )

                    # Try to extract complete JSON objects from the buffer
                    # Look for JSON object boundaries (assuming newline-delimited JSON)
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        if line.strip():  # Skip empty lines
                            try:
                                decoded_json = orjson.loads(line)
                                model_obj = _route.response_model(**decoded_json)
                                yield model_obj
                            except Exception as e:
                                self.log.error(f"Error decoding JSON: {line}")
                                raise BBOTServerError(f"Error decoding JSON: {line}") from e

                # Process any remaining data in the buffer after the stream ends
                if buffer.strip():
                    try:
                        decoded_json = orjson.loads(buffer)
                        model_obj = _route.response_model(**decoded_json)
                        yield model_obj
                    except Exception as e:
                        self.log.error(f"Error decoding final chunk: {buffer}")
                        raise BBOTServerError(f"Error decoding final chunk: {buffer}") from e
        except Exception as e:
            raise BBOTServerError(f"Error making {method} request -> {_url}: {e}") from e

    async def _websocket_request(self, _url, _route, *args, **kwargs) -> AsyncGenerator:
        """
        Creates a websocket connection, and yields messages from the server
        """
        method, _url, kwargs = self._prepare_api_request(_url, _route, *args, **kwargs)

        # replace scheme with ws
        _url = _url.replace("http://", "ws://").replace("https://", "wss://")
        try:
            async for websocket in connect(_url):
                async for message in websocket:
                    decoded_json = orjson.loads(message)
                    model_obj = _route.response_model(**decoded_json)
                    yield model_obj
        except asyncio.CancelledError:
            pass
        except RuntimeError as e:
            self.log.debug(f"Unexpected error in websocket stream: {e}")
        except Exception as e:
            raise BBOTServerError(f"Error in websocket stream at {_url}: {e}") from e

    async def _websocket_publish(self, _url, _route, message_generator, *args, **kwargs):
        """
        Creates a websocket connection, and sends messages to the server
        """
        method, _url, kwargs = self._prepare_api_request(_url, _route, *args, **kwargs)

        _url = _url.replace("http://", "ws://").replace("https://", "wss://")
        try:
            async for message in message_generator:
                async for websocket in connect(_url):
                    await websocket.send(message)
        except Exception as e:
            raise BBOTServerError(f"Error in websocket stream at {_url}: {e}") from e

    def _prepare_http_body(self, method, kwargs):
        # body
        body = None

        # if we're doing a GET and there's leftover args, something is wrong
        if method == "GET":
            if kwargs:
                raise ValueError(f"Unknown arguments: {','.join(kwargs)}")
        else:
            # if we only have one kwarg left, it's the whole body
            if len(kwargs) == 1:
                body = kwargs.popitem()[-1]
            # otherwise, we make it a dictionary
            else:
                body = kwargs

        return body

    def _prepare_api_request(self, _url, _route, *args, **kwargs):
        """
        Determine the method, path, and query params for the request

        Used to construct HTTP requests, streams, and websocket connections
        """
        # HTTP route
        methods = getattr(_route.fastapi_route, "methods", []) or ["GET"]
        method = sorted(methods)[0]

        # convert any args into kwargs
        bound_args = _route.function_signature.bind(*args, **kwargs)
        bound_args.apply_defaults()
        kwargs = bound_args.arguments

        # convert kwargs into raw JSON for web request
        kwargs = jsonable_encoder(kwargs)

        fastapi_route = _route.fastapi_route

        # path params
        if fastapi_route.dependant.path_params:
            path_params = {}
            for param in fastapi_route.dependant.path_params:
                with suppress(AttributeError):
                    param = param.name
                value = kwargs.pop(param)
                path_params[param] = value

            # URL encode path parameters before formatting
            encoded_path_params = {k: quote(str(v), safe=self._url_safe_chars) for k, v in path_params.items()}
            _url = _url.format(**encoded_path_params)

        # query params
        if fastapi_route.dependant.query_params:
            query_params = {}
            for param in fastapi_route.dependant.query_params:
                with suppress(AttributeError):
                    param = param.name
                value = kwargs.pop(param)
                query_params[param] = value
            _url = self.add_query_params(_url, query_params)

        return method, _url, kwargs

    def add_query_params(self, url, new_params):
        """
        Given a URL and a dictionary of query parameters, add the parameters to the URL in the format of a query string and return the new URL
        """
        # Parse the URL into its components
        scheme, netloc, path, params, query, fragment = urlparse(url)
        # Create a dictionary of existing query parameters
        query_dict = parse_qs(query)
        # Update with new parameters
        for k, v in new_params.items():
            if v is not None:
                query_dict[k] = [v]
        # Encode the updated query string
        new_query = urlencode(query_dict, doseq=True)
        # Reconstruct the URL with new query string
        return urlunparse((scheme, netloc, path, params, new_query, fragment))

    def __getattr__(self, attr):
        """
        For every attribute, try to find a matching route in the route map and return a coroutine that will make the request

        If the attribute isn't found in the route map, just return the attribute from the applet

        _wrap is used here to allow the coroutine to be called synchronously
        """
        # if the attribute is a route, prepare the request
        applet = self.__getattribute__("applet")
        try:
            route = applet.route_maps[attr]
            url = f"{self.base_url}{route.full_path}"
            if route.endpoint_type == "http":
                coro = partial(self._http_request, url, route)
            elif route.endpoint_type == "http_stream":
                coro = partial(self._http_stream, url, route)
            elif route.endpoint_type == "websocket_stream_outgoing":
                coro = partial(self._websocket_request, url, route)
            elif route.endpoint_type == "websocket_stream_incoming":
                coro = partial(self._websocket_publish, url, route)
            else:
                raise ValueError(f"Unknown endpoint type: {route.endpoint_type}")
            return coro
        # otherwise just return the attribute as is
        except (KeyError, AttributeError):
            return getattr(applet, attr)

    def __dir__(self):
        """
        Makes sure that even with the __getattr__ override, the user can still see all the attributes of the applet

        Useful for tab completion in IDEs
        """
        return sorted(set(self.applet.route_maps.keys()) | set(dir(self.applet)))
