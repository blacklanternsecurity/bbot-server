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

    # must define model
    model = None

    # optionally you can include other applets
    include_apps = []

    # whether to nest this applet under its own path
    nested = True

    def __init__(self, backend, parent=None):
        self.log = logging.getLogger(f"bbot.io.{self.name.lower()}")
        self.backend = backend
        self.parent = parent
        self.child_applets = []
        self.router = APIRouter()

        # automatically add API routes for any methods marked with @api_endpoint decorator
        for attr in dir(self):
            val = getattr(self, attr)
            endpoint = getattr(val, "_endpoint", None)
            if callable(val) and endpoint is not None:
                kwargs = dict(getattr(val, "_kwargs", {}))
                endpoint_type = kwargs.pop("type", "http")
                if endpoint_type == "http":
                    kwargs["tags"] = [self.tag]
                    self.router.add_api_route(endpoint, val, **kwargs)
                elif endpoint_type == "websocket":
                    self.router.add_api_websocket_route(endpoint, val, **kwargs)

        for app in self.include_apps:
            self.include_app(app)

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
        self.log.info(f"Including {app_name}")
        app_name_lower = app_name.lower()
        # import the app
        module = importlib.import_module(f"bbot_io.applets.{app_name_lower}")
        # get its class
        app_class = getattr(module, app_name)
        # instantiate it
        applet = app_class(self.backend, parent=self)
        # set it as an attribute on self
        setattr(self, app_name_lower, applet)
        # add it to our FastAPI router
        if applet.nested:
            self.router.include_router(applet.router, prefix=f"/{app_name_lower}")
        else:
            self.router.include_router(applet.router)
        # add it to our list of child apps
        self.child_applets.append(applet)

    @property
    def name(self):
        return self.__class__.__name__

    @property
    def tag(self):
        if self.parent is None:
            return ""
        if self.nested and self.parent.parent is not None:
            return f"{self.parent.name} -> {self.name}"
        return self.name

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
