import httpx
import orjson
import logging
from functools import partial
from websockets import connect
from contextlib import suppress
from typing import AsyncGenerator
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode

# for converting pydantic objects into raw JSON
from fastapi.encoders import jsonable_encoder

# for converting raw JSON into pydantic objects
from pydantic import TypeAdapter

from bbot_server.interfaces._base import BaseInterface


log = logging.getLogger("bbot.server.http")


class http(BaseInterface):
    def __init__(self, url="http://localhost:8807/v1/", **kwargs):
        super().__init__(**kwargs)
        self.base_url = url.strip("/")
        self.client = httpx.AsyncClient()

    @property
    def options(self):
        options = dict(self.applet.backend.options)
        options.update(
            {
                "url": "URL of BBOT server",
            }
        )
        return options

    async def _request(self, _url, _route, *args, **kwargs):
        """
        Builds and issues a web request to the bbot server REST API

        Uses the API route to figure out the format etc.
        """
        method, _url, kwargs = self.prepare_api_request(_url, _route, *args, **kwargs)

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

        response = await self.client.request(url=_url, method=method, json=body)
        try:
            response_json = response.json()
        except Exception as e:
            print(f"Error decoding response json for {response}: {e}: {getattr(response, 'text', '')}")
            raise

        # if our function doesn't have a return type, return the raw JSON
        if _route.response_model is None:
            return response_json

        # otherwise, convert into format matching the return type of the function
        try:
            return TypeAdapter(_route.response_model).validate_python(response_json)
        except Exception as e:
            print(f"Error validating response json for {method}->{_url}: response: {response_json}: {e}")
            raise

    async def _websocket_request(self, _url, _route, *args, **kwargs) -> AsyncGenerator:
        """
        Similar to _request(), but creates a websocket connection instead of an HTTP request

        Returns an async generator that yields websocket messages
        """
        method, _url, kwargs = self.prepare_api_request(_url, _route, *args, **kwargs)

        # replace scheme with ws
        _url = _url.replace("http://", "ws://").replace("https://", "wss://")

        async with connect(_url) as ws:
            while True:
                message = await ws.recv()
                decoded_json = orjson.loads(message)
                model_obj = _route.response_model(**decoded_json)
                yield model_obj

    def prepare_api_request(self, _url, _route, *args, **kwargs):
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
            _url = _url.format(**path_params)

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

    def add_query_params(self, url, params):
        """
        Given a URL and a dictionary of query parameters, add the parameters to the URL in the format of a query string and return the new URL
        """
        # Parse the URL into its components
        scheme, netloc, path, params, query, fragment = urlparse(url)
        # Create a dictionary of existing query parameters
        query_dict = parse_qs(query)
        # Update with new parameters
        query_dict.update(params)
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
        try:
            route = self.applet.route_maps[attr]
            url = f"{self.base_url}{route.full_path}"
            if route.endpoint_type == "http":
                coro = partial(self._request, url, route)
            elif route.endpoint_type == "websocket":
                coro = partial(self._websocket_request, url, route)
            return self._wrap(coro)
        except KeyError:
            return self._wrap(getattr(self.applet, attr))

    def __dir__(self):
        """
        Makes sure that even with the __getattr__ override, the user can still see all the attributes of the applet

        Useful for tab completion in IDEs
        """
        return sorted(set(self.applet.route_maps.keys()) | set(dir(self.applet)))
