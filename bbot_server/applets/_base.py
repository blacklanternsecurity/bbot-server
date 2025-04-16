import re
import asyncio
import inspect
import logging
from omegaconf import OmegaConf
from typing import Annotated, Any  # noqa
from functools import cached_property
from pydantic import BaseModel, Field  # noqa
from pymongo import WriteConcern, ASCENDING
from fastapi import APIRouter

from bbot.models.pydantic import Event
from bbot_server.utils.misc import utc_now
from bbot_server.applets._routing import ROUTE_TYPES
from bbot_server.models.activity_models import Activity

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

    # BBOT activity types this applet watches
    watched_activities = []

    # the pydantic model this applet uses
    model = None

    # optionally you can include other applets
    include_apps = []

    # whether to nest this applet under its parent
    # this is typically true for every applet except the root
    _nested = True

    # optionally override route prefix
    _route_prefix = None

    def __init__(self, parent=None):
        # TODO: we need to collect all the child applets before doing any fastapi setup

        self.child_applets = []
        self.log = logging.getLogger(f"bbot_server.{self.name.lower()}")
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

        # stores the interface (http, python, etc. for convenience)
        self._interface = None

        # whether this is the primary instance of BBOT server
        # e.g. the one hosting the REST API / the one agents connect to
        self._is_main_server = False

    async def refresh(self, asset, events_by_type):
        """
        After an archive completes, we iterate through each host, and pass it into this function

        This function then collects the relevant events and compares them to the current state of the asset, making updates if necessary.

        This mainly for identifying outdated open ports, technologies, etc., and removing them from the asset.
        """
        return []

    async def _setup(self):
        if self._setup_finished:
            return

        await self._global_setup()

        if self.is_native:
            await self._native_setup()

        # set up children
        for child_applet in self.child_applets:
            await child_applet._setup()

        self._setup_finished = True

    async def _global_setup(self):
        """
        This setup always runs, regardless of which interface is being used.
        """
        pass

    async def _native_setup(self):
        """
        This setup only runs when BBOT server is running natively, e.g. directly connecting to mongo, redis, etc.
        """
        # inherit config, db, message queue, etc. from parent applet
        if self.parent is not None:
            self.asset_store = self.parent.asset_store
            self.asset_db = self.parent.asset_db
            self.asset_fs = self.parent.asset_fs

            self.user_store = self.parent.user_store
            self.user_db = self.parent.user_db
            self.user_fs = self.parent.user_fs

            self.event_store = self.parent.event_store
            self.message_queue = self.parent.message_queue
            self.task_broker = self.parent.task_broker

            # if model isn't defined, inherit from parent
            if self.model is None:
                self.model = self.parent.model
                self.collection = self.parent.collection
                self.strict_collection = self.parent.strict_collection
            else:
                # otherwise, set up applet-specific db tables
                self.table_name = getattr(self.model, "__tablename__", None)
                self.is_user_data = getattr(self.model, "__user__", False)
                if self.is_user_data:
                    self.db = self.user_db
                else:
                    self.db = self.asset_db

                if self.table_name is None:
                    self.collection = self.parent.collection
                    self.strict_collection = self.parent.strict_collection
                else:
                    self.collection = self.db[self.table_name]
                    # WriteConcern options:
                    #  w=1: Acknowledges the write operation only after it has been written to the primary. (the default)
                    #  j=True: Ensures the write operation is committed to the journal. (default is False)
                    # This helps prevent duplicates in asset activity.
                    self.strict_collection = self.collection.with_options(write_concern=WriteConcern(w=1, j=True))

                if self.collection is not None:
                    # build indexes
                    await self.build_indexes(self.model)

        # taskiq broker
        if self.task_broker is None:
            # taskiq broker
            self.task_broker = await self.message_queue.make_taskiq_broker()
            await self.task_broker.startup()

        # register watchdog tasks
        await self.register_watchdog_tasks(self.task_broker)

        if self.name != "Root Applet":
            await self.setup()

    async def build_indexes(self, model):
        if not model:
            return
        for fieldname, field in model.model_fields.items():
            if "indexed" in field.metadata:
                unique = "unique" in field.metadata
                await self.collection.create_index([(fieldname, ASCENDING)], unique=unique)
            elif "indexed_text" in field.metadata:
                await self.collection.create_index([(fieldname, "text")])

    async def register_watchdog_tasks(self, broker):
        # register watchdog tasks
        methods = {name: member for name, member in inspect.getmembers(self) if callable(member)}
        for method_name, method in methods.items():
            # handle case where tasks have already been registered
            method = getattr(method, "original_func", method)

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
            self.log.debug(f"Registering task: {method_name} {kwargs}")
            task = broker.register_task(method, **kwargs)
            # overwrite the original method with the decorated TaskIQ task
            setattr(self, method_name, task)

    async def setup(self):
        pass

    async def _cleanup(self):
        for child_applet in self.child_applets:
            await child_applet.cleanup()
            await child_applet._cleanup()

    async def cleanup(self):
        pass

    async def handle_activity(self, activity: Activity):
        pass

    async def handle_event(self, event: Event, asset=None):
        return []

    def make_activity(self, *args, **kwargs):
        return Activity(*args, **kwargs)

    async def emit_activity(self, *args, **kwargs):
        if not kwargs and len(args) == 1 and isinstance(args[0], Activity):
            activity = args[0]
        else:
            activity = Activity(*args, **kwargs)
        await self._emit_activity(activity)

    async def _emit_activity(self, activity: Activity):
        await self.root.message_queue.publish_asset(activity)

    def include_app(self, app_class):
        self.log.debug(f"{self.__class__.__name__} including {app_class.__name__}")
        # instantiate it
        applet = app_class(parent=self)
        # set it as an attribute on self
        setattr(self, applet.name_lowercase, applet)

        if applet._nested or self.parent is None:
            router = self.router
        else:
            router = self.parent.router
        # add it to our FastAPI router
        router.include_router(applet.router)
        # add it to our list of child apps
        self.child_applets.append(applet)
        return applet

    async def _get_obj(self, host: str, kwargs):
        """
        Shorthand for getting an object (matching the applet's model) from the asset store
        """
        query = {"host": host, "type": self.model.__name__}
        obj = await self.collection.find_one(query, kwargs)
        if not obj:
            raise self.BBOTServerNotFoundError(f"Object of type {self.model.__name__} for host {host} not found")
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

    def all_child_applets(self, include_self=False):
        applets = []
        if include_self:
            applets.append(self)
        for applet in self.child_applets:
            applets.extend(applet.all_child_applets(include_self=True))
        return applets

    def ensure_main_server(self):
        """
        Makes sure we are in the main instance of BBOT server.
        """
        if not self.is_main_server:
            raise self.BBOTServerValueError("This endpoint is only available on the main server instance")

    def watches_event(self, event_type):
        if "*" in self.watched_events:
            return True
        return event_type in self.watched_events

    def watches_activity(self, activity_type):
        if "*" in self.watched_activities:
            return True
        return activity_type in self.watched_activities

    @property
    def is_main_server(self):
        return self.root._is_main_server

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
                fastapi_kwargs = dict(getattr(function, "_kwargs", {}))
                endpoint_type = fastapi_kwargs.pop("type", "http")
                response_model = fastapi_kwargs.pop("response_model", None)

                try:
                    route_class = ROUTE_TYPES[endpoint_type]
                except KeyError:
                    raise self.BBOTServerError(f"Invalid endpoint type: {endpoint_type}")

                kwargs = {"tags": [self.tag]}

                if route_class.requires_response_model:
                    if response_model is None:
                        raise self.BBOTServerError(
                            f"{self.name}.{function.__name__} {endpoint}: Must specify a pydantic model used for deserializing {endpoint_type} streams"
                        )
                    kwargs["response_model"] = response_model

                bbot_server_route = route_class(function, **kwargs)
                bbot_server_route.add_to_applet(self)

    @property
    def config(self):
        return self.root._config

    @property
    def tag(self):
        if self.parent is None:
            return ""
        if self._nested and self.parent.parent is not None:
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
            if self._nested:
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
    def interface(self):
        return self.root._interface

    @property
    def interface_type(self):
        return self.root._interface_type

    @property
    def is_native(self):
        """
        Whether this instance of BBOT server is running natively (e.g. not through the HTTP interface)

        When this is True, we can safely skip any database/message-queue functionality.
        """
        return self.interface_type == "python"

    def utc_now(self):
        return utc_now()

    def __getattr__(self, name):
        # try getting the attribute from all the child applets
        for child_applet in getattr(self, "child_applets", []):
            try:
                return getattr(child_applet, name)
            except AttributeError:
                continue
        raise AttributeError(f'{self.__class__.__name__} has no attribute "{name}"')

    ### ASYNC UTILS FOR CONVENIENCE ###

    CancelledError = asyncio.CancelledError

    async def sleep(self, *args, **kwargs):
        await asyncio.sleep(*args, **kwargs)

    def create_task(self, *args, **kwargs):
        return asyncio.create_task(*args, **kwargs)

    ### BBOT IMPORTS FOR CONVENIENCE ###

    from bbot_server.errors import BBOTServerError, BBOTServerNotFoundError, BBOTServerValueError
