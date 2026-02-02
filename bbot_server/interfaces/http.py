import httpx
import string
import orjson
import typing
import asyncio
import traceback
from functools import partial
from websockets import connect
from contextlib import suppress
from typing import AsyncGenerator
from contextlib import contextmanager
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode, quote


# for converting pydantic objects into raw JSON
from fastapi.encoders import jsonable_encoder

# for converting raw JSON into pydantic objects
from pydantic import TypeAdapter

from bbot_server.config import BBOT_SERVER_CONFIG as bbcfg
from bbot_server.interfaces.base import BaseInterface
from bbot_server.utils.async_utils import async_to_sync_class
from bbot_server.errors import HTTP_STATUS_MAPPINGS, BBOTServerError
from bbot_server.utils.misc import smart_encode, detect_translatable_function, convert_human_args

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

    def __init__(self, url=None, **kwargs):
        super().__init__(**kwargs)
        if url is None:
            if not hasattr(self.config, "url"):
                raise ValueError("When using the HTTP interface, url is required in the config")
            url = self.config.url
        self.base_url = url.strip("/")
        self._http_timeout = getattr(self.config.cli, "http_timeout", 90)
        self._client = None

    @property
    def config(self):
        return bbcfg

    async def _http_request(self, _url, _route, *args, **kwargs):
        """
        Builds and issues a web request to the bbot server REST API

        Uses the API route to figure out the format etc.
        """
        method, _url, kwargs = self._prepare_api_request(_url, _route, *args, **kwargs)
        try:
            body = self._prepare_http_body(method, kwargs)
        except ValueError as e:
            raise BBOTServerError(f"Error preparing HTTP body for {method} request -> {_url}: {e}") from e

        async def warn_if_slow():
            await asyncio.sleep(5)
            self.log.warning(
                f"{method} request to {_url} is taking a while; if you requested a lot of data (or a summary of a lot of data), this is normal"
            )

        request_task = asyncio.create_task(
            self.client.request(
                url=_url, method=method, json=body, headers={bbcfg.auth_header: str(bbcfg.get_api_key())}
            )
        )
        warn_task = asyncio.create_task(warn_if_slow())

        log.debug(f"{method} request -> {_url}")
        await asyncio.wait([request_task, warn_task], return_when=asyncio.FIRST_COMPLETED)

        # if the request finished first, cancel the warning task
        with suppress(asyncio.CancelledError):
            warn_task.cancel()
            await warn_task

        with self._handle_httpx_error(method, _url):
            response = await request_task

        response_json = await self._check_response_error(response)

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
        print(f"url: {_url}, kwargs {kwargs}")
        try:
            body = self._prepare_http_body(method, kwargs)
        except ValueError as e:
            raise BBOTServerError(f"Error preparing HTTP body for {method} request -> {_url}: {e}") from e

        buffer = b""
        MAX_BUFFER_SIZE = 10 * 1024 * 1024  # 10 MB max buffer size

        with self._handle_httpx_error(method, _url):
            log.debug(f"Streaming {method} request -> {_url}")
            async with self.client.stream(method=method, url=_url, json=body) as response:
                await self._check_response_error(response, return_json=False)
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

    async def _websocket_request(self, _url, _route, *args, **kwargs) -> AsyncGenerator:
        """
        Creates a websocket connection, and yields messages from the server
        """
        method, _url, kwargs = self._prepare_api_request(_url, _route, *args, **kwargs)

        # replace scheme with ws
        _url = _url.replace("http://", "ws://").replace("https://", "wss://")
        try:
            async for websocket in connect(_url, additional_headers={bbcfg.auth_header: str(bbcfg.get_api_key())}):
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
            async with connect(_url, additional_headers={bbcfg.auth_header: str(bbcfg.get_api_key())}) as websocket:
                async for message in message_generator:
                    message = smart_encode(message)
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

        fn = _route.orig_function

        # if needed, translate individual human friendly kwargs into a pydantic model
        param_name, model_class = detect_translatable_function(fn)
        if param_name is not None:
            args, kwargs = convert_human_args(fn, param_name, model_class, *args, **kwargs)

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

    @property
    def client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._http_timeout, headers={bbcfg.auth_header: str(bbcfg.get_api_key())}
            )
        return self._client

    def __getattr__(self, attr):
        """
        For every attribute, try to find a matching route in the route map and return a coroutine that will make the request

        If the attribute isn't found in the route map, just return the attribute from the applet
        """
        # if the attribute is a route, prepare the request
        bbot_server = self.__getattribute__("bbot_server")
        try:
            route = bbot_server.route_maps[attr]
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
            return getattr(bbot_server, attr)

    def __dir__(self):
        """
        Makes sure that even with the __getattr__ override, the user can still see all the attributes of the applet

        Useful for tab completion in IDEs
        """
        return sorted(set(self.bbot_server.route_maps.keys()) | set(dir(self.bbot_server)))

    @contextmanager
    def _handle_httpx_error(self, method, _url):
        try:
            yield
        except httpx.HTTPError as e:
            raise BBOTServerError(f"Error making {method} request -> {_url}: {e}") from e
        except BBOTServerError:
            raise
        except Exception as e:
            self.log.critical(traceback.format_exc())
            raise BBOTServerError(f"Error making {method} request -> {_url}: {e}") from e

    async def _check_response_error(self, response, return_json=True):
        response_json = None

        if return_json or not response.is_success:
            try:
                # if it's a streaming response, read the body
                if isinstance(response.stream, typing.AsyncIterable):
                    await response.aread()
                response_json = response.json()
            except Exception as e:
                self.log.warning(f"Error decoding response json for {response}: {e} - {getattr(response, 'text', '')}")
                raise BBOTServerError(f"Error decoding response JSON for {response}: {e}") from e

        if not response.is_success:
            if isinstance(response_json, dict) and "error" in response_json:
                error_class = HTTP_STATUS_MAPPINGS.get(response.status_code, BBOTServerError)
                raise error_class(response_json["error"], detail=response_json.get("detail", {}))

            raise BBOTServerError(
                f"Error making {response.request.method} request -> {response.url}: {response.status_code} {response.text}"
            )

        return response_json
