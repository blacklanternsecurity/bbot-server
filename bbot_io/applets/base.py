import importlib
from fastapi import APIRouter


def api_endpoint(endpoint, **kwargs):
    def decorator(fn):
        fn._kwargs = kwargs
        fn._endpoint = endpoint
        return fn

    return decorator


class BaseApplet:
    # must define model
    model = None

    def __init__(self, backend, parent=None):
        self.backend = backend
        self.parent = parent
        self.router = APIRouter()
        self.child_applets = []

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

    async def setup(self):
        await self.backend.setup()
        self.db = await self.backend.get_table(self)
        for child_applet in self.child_applets:
            await child_applet.setup()

    def include_app(self, app_name):
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
        # self.router.include_router(applet.router, prefix=f"/{app_name_lower}")
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
        if self.parent.parent is not None:
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
