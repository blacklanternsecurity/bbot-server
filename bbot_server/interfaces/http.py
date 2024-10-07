import httpx
import logging
from functools import partial
from contextlib import suppress
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode

# for converting pydantic objects into raw JSON
from fastapi.encoders import jsonable_encoder

# for converting raw JSON into pydantic objects
from pydantic import TypeAdapter

from bbot_server.interfaces._base import BaseInterface


log = logging.getLogger("bbot.server.http")


class HTTPInterface(BaseInterface):

    def __init__(self, applet, url, **kwargs):
        super().__init__(applet, **kwargs)
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

    async def _request(self, _url, _route, _signature, *args, **kwargs):
        """
        Builds and issues a web request to the bbot server REST API

        Uses the API route to figure out the format etc.
        """
        # HTTP route
        method = sorted(_route.methods)[0]

        # convert any args into kwargs
        bound_args = _signature.bind(*args, **kwargs)
        bound_args.apply_defaults()
        kwargs = bound_args.arguments

        # convert kwargs into raw JSON for web request
        kwargs = jsonable_encoder(kwargs)

        # path params
        if _route.dependant.path_params:
            path_params = {}
            for param in _route.dependant.path_params:
                with suppress(AttributeError):
                    param = param.name
                value = kwargs.pop(param)
                path_params[param] = value
            _url = _url.format(**path_params)

        # query params
        if _route.dependant.query_params:
            query_params = {}
            for param in _route.dependant.query_params:
                with suppress(AttributeError):
                    param = param.name
                value = kwargs.pop(param)
                query_params[param] = value
            _url = self.add_query_params(_url, kwargs)

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
        return TypeAdapter(_route.response_model).validate_python(response_json)

    def add_query_params(self, url, params):
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
        try:
            full_path, route, signature = self.applet.route_maps[attr]
            url = f"{self.base_url}{full_path}"
            coro = partial(self._request, url, route, signature)
            return self._wrap(coro)
        except KeyError:
            return self._wrap(getattr(self.applet, attr))
