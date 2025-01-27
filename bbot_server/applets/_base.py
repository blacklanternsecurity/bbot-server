import logging
import importlib
from pymongo import WriteConcern
from pydantic import BaseModel, Field  # noqa
from fastapi import APIRouter, HTTPException

from bbot.models.pydantic import Event
from bbot_server.config import BBOT_SERVER_CONFIG
from bbot_server.utils.async_utils import NamedLock
from bbot_server.models.assets import Asset, AssetActivity
from bbot_server.applets._routing import BBOTServerRoute, WebSocketServerRoute, api_endpoint  # noqa


log = logging.getLogger(__name__)


class BaseApplet:
    """
    Applets are the building blocks of BBOT server.

    They each have a collection of methods which double as API endpoints.

    Applets can be nested. They can have their own database tables.

    They can also subscribe to and produce asset activities.
    """

    description = ""

    # BBOT event types this applet watches
    watched_events = []

    # Custom fields to add to the asset
    class AssetFields(BaseModel):
        pass

    # optionally you can include other applets
    include_apps = []

    # whether to nest this applet under its parent
    nested = True

    # optionally override route prefix
    _route_prefix = None

    # the pydantic model this applet uses
    _data_model = None

    def __init__(self, parent=None):
        self.log = logging.getLogger(f"bbot.server.{self.name.lower()}")
        self.config = BBOT_SERVER_CONFIG
        self.parent = parent
        self.child_applets = []
        self.router = APIRouter(prefix=self.route_prefix)
        self.route_maps = {}
        self.route_maps = self.root.route_maps

        # this is used when running read/write operations on an asset
        self._asset_lock = NamedLock()

        self.asset_store = None
        self.event_store = None
        self.message_queue = None

        self._add_custom_routes()

        self.model = None
        if self._data_model:
            self.model = self._data_model

        for app in self.include_apps:
            try:
                self.include_app(app)
            except Exception as e:
                print(f"Error including app {app}: {e}")
                import traceback

                traceback.print_exc()

        self._setup_finished = False

    async def _setup(self):
        if self._setup_finished:
            return

        # inherit database connections, message queue, etc.
        if self.parent is not None:
            self.asset_store = self.parent.asset_store
            self.event_store = self.parent.event_store
            self.message_queue = self.parent.message_queue

            if self.model is None:
                self.model = self.parent.model

        if self.model is not None:
            self.table_name = getattr(self.model, "__tablename__", None)
            if self.table_name is not None:
                self.collection = self.asset_store.db[self.table_name]
                # WriteConcern options:
                #  w=1: Acknowledges the write operation only after it has been written to the primary. (the default)
                #  j=True: Ensures the write operation is committed to the journal. (default is False)
                # This helps prevent duplicates in asset activity.
                self.strict_collection = self.collection.with_options(write_concern=WriteConcern(w=1, j=True))

        # set up children
        for child_applet in self.child_applets:
            await child_applet._setup()

        self._setup_finished = True

    async def setup(self):
        pass

    async def _cleanup(self):
        await self.cleanup()
        for child_applet in self.child_applets:
            await child_applet.cleanup()

    async def cleanup(self):
        pass

    async def _ingest_event(self, asset: Asset, event: Event):
        watched_events = self.watched_events
        activities = []
        if event.type in watched_events:
            activities.extend(await self.ingest_event(asset, event))
        for child_applet in self.child_applets:
            child_activities = await child_applet._ingest_event(asset, event)
            activities.extend(child_activities)
        return activities

    async def ingest_event(self, asset: Asset, event: Event):
        return []

    async def emit_activity(self, activity: AssetActivity):
        await self.root.message_queue.asset_publish(activity.model_dump())

    def raise404(self, detail: str):
        raise HTTPException(status_code=404, detail=detail)

    def include_app(self, app_name):
        self.log.debug(f"Including {app_name}")
        app_name_lower = app_name.lower()
        # import the app
        module = importlib.import_module(f"bbot_server.applets.{app_name_lower}")
        # get its class
        app_class = getattr(module, app_name)
        # instantiate it
        applet = app_class(parent=self)
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

    @property
    def name_friendly(self):
        return self.name.replace("_", " ")

    @property
    def all_asset_models(self):
        asset_models = [self.AssetFields]
        for child_applet in self.child_applets:
            asset_models.extend(child_applet.all_asset_models)

    @property
    def all_fieldnames(self):
        fieldnames = self.fieldnames
        for child_applet in self.child_applets:
            fieldnames.extend(child_applet.all_fieldnames)
        return fieldnames

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
                    bbot_server_route = BBOTServerRoute(function, tags=[self.tag])
                elif endpoint_type == "websocket":
                    bbot_server_route = WebSocketServerRoute(function, tags=[self.tag])
                else:
                    raise ValueError(f"Invalid endpoint type: {endpoint_type}")
                bbot_server_route.add_to_applet(self)

    @property
    def tag(self):
        if self.parent is None:
            return ""
        if self.nested and self.parent.parent is not None:
            return f"{self.parent.name} -> {self.name_friendly}"
        return self.name_friendly

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
    def root(self):
        applet = self
        while getattr(applet, "parent", None) is not None:
            applet = applet.parent
        return applet

    @property
    def route_prefix(self):
        if self._route_prefix is not None:
            return self._route_prefix
        return f"/{self.name.lower()}"

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
        raise AttributeError(f'{self.__class__.__name__} has no attribute "{attr}"')
