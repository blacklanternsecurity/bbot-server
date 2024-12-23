import inspect
import logging
import importlib
from fastapi import APIRouter


def api_endpoint(endpoint, **kwargs):
    def decorator(fn):
        fn._kwargs = kwargs
        fn._endpoint = endpoint
        return fn

    return decorator


class BaseApplet:
    """
    Applets are where the core business logic lives.

    User --> Interface --> Applets --> Backend
    """

    description = ""

    data_model = None

    # optionally you can include other applets
    include_apps = []

    # whether to nest this applet under its own path
    nested = True

    # optionally override route prefix
    _route_prefix = None

    def __init__(self, backend, parent=None):
        self.log = logging.getLogger(f"bbot.server.{self.name.lower()}")
        self.backend = backend
        self.parent = parent
        self.child_applets = []
        self.router = APIRouter(prefix=self.route_prefix)
        self.route_maps = {}
        self.route_maps = self.highest_parent.route_maps

        self._add_custom_routes()

        self.model = None
        if self.data_model:
            self.model = self.data_model

        for app in self.include_apps:
            self.include_app(app)

    @property
    def route_prefix(self):
        if self._route_prefix is not None:
            return self._route_prefix
        return f"/{self.name.lower()}"

    async def setup(self):
        # backend first
        await self.backend._setup()
        self.db = await self.backend.make_table(self)
        # inherit db, model from parent
        if self.parent is not None:
            if self.db is None:
                self.db = self.parent.db
            if self.model is None:
                self.model = self.parent.model
        # then children
        for child_applet in self.child_applets:
            await child_applet.setup()

    def include_app(self, app_name):
        self.log.debug(f"Including {app_name}")
        app_name_lower = app_name.lower()
        # import the app
        module = importlib.import_module(f"bbot_server.applets.{app_name_lower}")
        # get its class
        app_class = getattr(module, app_name)
        # instantiate it
        applet = app_class(self.backend, parent=self)
        # set it as an attribute on self
        setattr(self, app_name_lower, applet)

        if applet.nested or self.parent is None:
            router = self.router
        else:
            router = self.parent.router
        # add it to our FastAPI router
        router.include_router(applet.router)
        # add it to our list of child apps
        self.child_applets.append(applet)

    @property
    def name(self):
        return self.__class__.__name__

    def _add_custom_routes(self):
        # automatically add API routes for any methods marked with @api_endpoint decorator
        # for every attribute on this class
        for attr in dir(self):
            # get its value
            function = getattr(self, attr, None)
            # see if the value has an "_endpoint" attribute
            endpoint = getattr(function, "_endpoint", None)
            # if it's a callable function and it has _endpoint, it's an @api_endpoint
            if callable(function) and endpoint is not None:
                kwargs = dict(getattr(function, "_kwargs", {}))
                endpoint_type = kwargs.pop("type", "http")
                if endpoint_type == "http":
                    kwargs["tags"] = [self.tag]
                    self.router.add_api_route(endpoint, function, **kwargs)
                elif endpoint_type == "websocket":
                    self.router.add_api_websocket_route(endpoint, function, **kwargs)

                # keep mapping of function names -> HTTP endpoints
                route = self.router.routes[-1]
                full_path = f"{self.full_prefix()}{route.path}"
                signature = inspect.signature(function)
                self.route_maps[function.__name__] = (full_path, route, signature)

    @property
    def tag(self):
        if self.parent is None:
            return ""
        if self.nested and self.parent.parent is not None:
            return f"{self.parent.name} -> {self.name}"
        return self.name

    @property
    def tags_metadata(self):
        tags = []
        if self.tag and self.description:
            tags.append({"name": self.tag, "description": self.description})
        for child_applet in self.child_applets:
            tags.extend(child_applet.tags_metadata)
        return tags

    def full_prefix(self, include_self=False):
        prefix = ""
        if include_self:
            prefix = self.router.prefix
        parent_prefix = ""
        if self.parent is not None:
            if self.nested:
                parent_prefix = self.parent.full_prefix(include_self=True)
        return f"{parent_prefix}{prefix}"

    @property
    def highest_parent(self):
        applet = self
        while getattr(applet, "parent", None) is not None:
            applet = applet.parent
        return applet

    def __getattribute__(self, attr):
        try:
            # first try self
            return super().__getattribute__(attr)
        except AttributeError:
            # then try all the child applets
            for child_applet in self.child_applets:
                try:
                    return getattr(child_applet, attr)
                except AttributeError:
                    continue
        raise AttributeError(f'Applet has no attribute "{attr}"')
