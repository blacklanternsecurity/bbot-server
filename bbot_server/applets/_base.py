import re
import asyncio
import inspect
import logging
from omegaconf import OmegaConf
from pymongo import WriteConcern
from typing import Annotated, Any  # noqa
from functools import cached_property
from pydantic import BaseModel, Field  # noqa
from fastapi import APIRouter, HTTPException

from bbot.models.pydantic import Event
from bbot_server.models.assets import AssetActivity
from bbot_server.applets._routing import HTTPRoute, HTTPStreamRoute, WebsocketRoute, WebsocketStreamRoute

word_regex = re.compile(r"\W+")


log = logging.getLogger(__name__)


def api_endpoint(endpoint, **kwargs):
    """
    Decorate your applet method with this to add it to FastAPI
    """

    def decorator(fn):
        fn._kwargs = kwargs
        fn._endpoint = endpoint
        return fn

    return decorator


def watchdog_task(**kwargs):
    """
    Decorate your applet method with this to make it a watchdog task
    """

    def decorator(fn):
        fn._kwargs = kwargs
        fn._watchdog_task = True
        return fn

    return decorator


class BaseApplet:
    """
    Applets are the building blocks of BBOT server.

    They each have a collection of methods which double as API endpoints.

    Applets can be nested. They can have their own database tables.

    They can also subscribe to and produce asset activities.
    """

    # friendly human name of the applet
    name = "Base Applet"

    # friendly human description of the applet
    description = ""

    # BBOT event types this applet watches
    watched_events = []

    # the pydantic model this applet uses
    model = None

    # optionally you can include other appletsP
    include_apps = []

    # optionally include watchdogs
    include_watchdogs = []

    # whether to nest this applet under its parent
    nested = True

    # optionally override route prefix
    _route_prefix = None

    # _asset_lock is used to prevent multiple simultaneous writes on the same asset
    # it's intentionally defined at the class level so it's shared between all the watchdogs
    _asset_lock = None

    def __init__(self, parent=None):
        self.child_applets = []
        self.log = logging.getLogger(f"bbot.server.{self.name.lower()}")
        self.parent = parent
        self.router = APIRouter(prefix=self.route_prefix)
        self.route_maps = {}
        self.route_maps = self.root.route_maps

        self.asset_store = None
        self.event_store = None
        self.message_queue = None
        self.task_broker = None

        # mongo stuff
        self.collection = None
        self.strict_collection = None

        self._add_custom_routes()

        for app in self.include_apps:
            try:
                self.include_app(app)
            except Exception as e:
                self.log.error(f"Error including app {app}: {e}")
                import traceback

                traceback.print_exc()

        self._setup_finished = False

    async def refresh(self, host: str):
        """
        After an archive completes, we iterate through each host, and pass it into this function

        This function then collects the relevant events and compares them to the current state of the asset, making updates if necessary.

        This mainly for identifying outdated open ports, technologies, etc., and removing them from the asset.
        """
        return []

    async def _setup(self):
        if self._setup_finished:
            return

        # inherit config, db, message queue, etc. from parent applet
        if self.parent is not None:
            self.config = self.parent.config
            self.asset_store = self.parent.asset_store
            self.event_store = self.parent.event_store
            self.message_queue = self.parent.message_queue
            self.collection = self.parent.collection
            self.strict_collection = self.parent.strict_collection
            self.task_broker = self.parent.task_broker

            if self.model is None:
                self.model = self.parent.model

        # database tables
        if self.model is not None:
            self.table_name = getattr(self.model, "__tablename__", None)
            if self.table_name is not None:
                self.collection = self.asset_store.db[self.table_name]
                # WriteConcern options:
                #  w=1: Acknowledges the write operation only after it has been written to the primary. (the default)
                #  j=True: Ensures the write operation is committed to the journal. (default is False)
                # This helps prevent duplicates in asset activity.
                self.strict_collection = self.collection.with_options(write_concern=WriteConcern(w=1, j=True))

        # create database indexes
        if self.model is not None:
            for fieldname, field in self.model.model_fields.items():
                if "indexed" in field.metadata:
                    unique = "unique" in field.metadata
                    # create mongodb index
                    await self.collection.create_index([(fieldname, 1)], unique=unique)
                elif "indexed_text" in field.metadata:
                    await self.collection.create_index([(fieldname, "text")])

        # taskiq broker
        if self.task_broker is None:
            # taskiq broker
            self.task_broker = await self.message_queue.make_taskiq_broker()
            await self.task_broker.startup()

        # register watchdog tasks
        await self.register_watchdog_tasks(self.task_broker)

        if self.name != "Root Applet":
            await self.setup()

        # set up children
        for child_applet in self.child_applets:
            await child_applet._setup()

        self._setup_finished = True

    async def register_watchdog_tasks(self, broker):
        # register watchdog tasks
        for child_applet in self.all_child_applets:
            methods = {name: member for name, member in inspect.getmembers(child_applet) if callable(member)}
            for method_name, method in methods.items():
                _watchdog_task = getattr(method, "_watchdog_task", None)
                if _watchdog_task is None:
                    continue
                kwargs = getattr(method, "_kwargs", {})
                # crontab handling
                cron_default = kwargs.pop("cron", None)
                cron_config_key = kwargs.pop("cron_config_key", None)
                if cron_config_key is not None:
                    if cron_default is None:
                        raise ValueError(
                            f"{self.name}.{method_name}: When specifying a crontab config value, you must also give a default crontab value (kwarg: 'cron')"
                        )
                    cron = OmegaConf.select(self.config, cron_config_key, default=cron_default)
                    kwargs["schedule"] = [{"cron": cron}]
                elif cron_default is not None:
                    kwargs["schedule"] = [{"cron": cron_default}]
                task = broker.register_task(method, **kwargs)
                setattr(child_applet, method_name, task)

    async def setup(self):
        pass

    async def _cleanup(self):
        await self.cleanup()
        for child_applet in self.child_applets:
            await child_applet.cleanup()

    async def cleanup(self):
        pass

    async def ingest_event(self, event: Event):
        return []

    async def emit_activity(self, *args, **kwargs):
        activity = AssetActivity(*args, **kwargs)
        await self._emit_activity(activity)

    async def _emit_activity(self, activity: AssetActivity):
        await self.root.message_queue.asset_publish(activity)

    def raise404(self, detail: str):
        raise HTTPException(status_code=404, detail=detail)

    def include_app(self, app_class):
        self.log.debug(f"{self.__class__.__name__} including {app_class.__name__}")
        # instantiate it
        applet = app_class(parent=self)
        # set it as an attribute on self
        setattr(self, applet.name_lowercase, applet)

        if applet.nested or self.parent is None:
            router = self.router
        else:
            router = self.parent.router
        # add it to our FastAPI router
        router.include_router(applet.router)
        # add it to our list of child apps
        self.child_applets.append(applet)

    async def _get_obj(self, host: str):
        """
        Shorthand for getting an object (matching the applet's model) from the asset store
        """
        obj = await self.collection.find_one({"$and": [{"host": host}, {"type": self.model.__name__}]})
        if not obj:
            return
        return self.model(**obj)

    async def _put_obj(self, obj):
        """
        Shorthand for writing an object into the applet's asset store
        """
        await self.collection.update_one(
            {"host": obj.host, "type": self.model.__name__}, {"$set": obj.model_dump()}, upsert=True
        )

    @cached_property
    def name_lowercase(self):
        # Replace non-alphanumeric characters with an underscore
        return word_regex.sub("_", self.name.lower())

    @property
    def all_child_applets(self):
        applets = [self]
        for applet in self.child_applets:
            applets.extend(applet.all_child_applets)
        return applets

    @property
    def all_asset_models(self):
        asset_models = [self.AssetFields]
        for child_applet in self.all_child_applets:
            asset_models.append(child_applet.AssetFields)
        return asset_models

    @property
    def all_fieldnames(self):
        fieldnames = self.fieldnames
        for child_applet in self.all_child_applets:
            fieldnames.extend(child_applet.fieldnames)
        return fieldnames

    def _add_custom_routes(self):
        # automatically add API routes for any methods marked with @api_endpoint decorator
        # for every attribute on this class
        for attr in dir(self):
            # get its value
            function = getattr(self, attr, None)
            if not callable(function):
                continue
            # see if the value has an "_endpoint" attribute
            endpoint = getattr(function, "_endpoint", None)
            # if it's a callable function and it has _endpoint, it's an @api_endpoint
            if endpoint is not None:
                kwargs = dict(getattr(function, "_kwargs", {}))
                endpoint_type = kwargs.pop("type", "http")
                response_model = kwargs.pop("response_model", None)
                if endpoint_type == "http":
                    bbot_server_route = HTTPRoute(function, tags=[self.tag])
                elif endpoint_type == "http_stream":
                    if response_model is None:
                        raise ValueError(
                            f"{self.name}.{function.__name__} {endpoint}: Must specify a pydantic model used for deserializing HTTP streams"
                        )
                    bbot_server_route = HTTPStreamRoute(function, tags=[self.tag], response_model=response_model)
                elif endpoint_type == "websocket":
                    bbot_server_route = WebsocketRoute(function, tags=[self.tag])
                elif endpoint_type == "websocket_stream":
                    if response_model is None:
                        raise ValueError(
                            f"{self.name}.{function.__name__} {endpoint}: Must specify a pydantic model used for deserializing websocket messages"
                        )
                    bbot_server_route = WebsocketStreamRoute(function, tags=[self.tag], response_model=response_model)
                else:
                    raise ValueError(f"Invalid endpoint type: {endpoint_type}")
                bbot_server_route.add_to_applet(self)

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

    @cached_property
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

    @property
    def asset_lock(self):
        if self.__class__._asset_lock is None:
            from bbot_server.utils.async_utils import NamedLock

            self.__class__._asset_lock = NamedLock()
        return self.__class__._asset_lock

    def __getattribute__(self, attr):
        """
        Allow access to attributes on any of this applet's children, recursively

        This saves you from having to do things like: `bbot_server.assets.scans.runs.get_scan_runs()`.
        Instead, you can just do: `bbot_server.get_scan_runs()`.
        """
        try:
            # first try self
            return super().__getattribute__(attr)
        except AttributeError:
            # then try all the child applets
            for child_applet in super().__getattribute__("child_applets"):
                try:
                    return getattr(child_applet, attr)
                except AttributeError:
                    continue
        raise AttributeError(f'{self.__class__.__name__} has no attribute "{attr}"')

    ### ASYNC UTILS FOR CONVENIENCE ###

    CancelledError = asyncio.CancelledError

    async def sleep(self, *args, **kwargs):
        await asyncio.sleep(*args, **kwargs)

    def create_task(self, *args, **kwargs):
        return asyncio.create_task(*args, **kwargs)
