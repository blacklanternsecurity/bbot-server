import re
import asyncio
from inspect import getmembers
import logging
import traceback

from fastapi import APIRouter
from omegaconf import OmegaConf
from typing import Annotated, Any, get_origin, get_args, Union, Callable, cast  # noqa
from functools import cached_property
from pydantic import BaseModel, Field  # noqa
from sqlalchemy import select, func, delete as sa_delete, update

from bbot_server.assets import Asset
from bbot.models.pydantic import Event
from bbot_server.modules import API_MODULES
from bbot.core.helpers import misc as bbot_misc
from bbot_server.utils import misc as bbot_server_misc
from bbot_server.applets._routing import make_bbotserver_route
from bbot_server.modules.activity.activity_models import Activity
from bbot_server.errors import BBOTServerError, BBOTServerValueError

word_regex = re.compile(r"\W+")

log = logging.getLogger(__name__)


def api_endpoint(endpoint: str, **kwargs):
    """
    Decorate your applet method with this to add it to FastAPI.

    Args:
        endpoint: The API endpoint path
        **kwargs: Additional FastAPI route kwargs
    """

    def decorator(fn):
        fn._kwargs = kwargs
        fn._endpoint = endpoint
        return bbot_server_misc.human_friendly_kwargs(fn)

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

    # which other applet should include this one
    # leave blank to attach to the root applet
    attach_to = ""

    # whether to nest this applet under its parent
    # this is typically true for every applet except the root
    _nested = True

    # optionally override route prefix
    _route_prefix = None

    # priority of this applet's handle_activity method, between 1 and 5, inclusive
    # higher numbers are higher priority
    # this is used to determine the order in which applets' .handle_activity methods are called
    _activity_priority = 3

    # priority of this applet's handle_event method, between 1 and 5, inclusive
    # higher numbers are higher priority
    # this is used to determine the order in which applets' .handle_event methods are called
    _event_priority = 3

    # BBOT helpers
    helpers = bbot_server_misc
    bbot_helpers = bbot_misc

    def __init__(self, parent=None):
        self.child_applets = []
        self.log = logging.getLogger(f"bbot_server.{self.name.lower()}")
        self.parent = parent
        self.router = APIRouter(prefix=self.route_prefix)
        self.route_maps = {}
        self.route_maps = self.root.route_maps

        self.message_queue = None
        self.task_broker = None

        # session factory for PostgreSQL (inherited from root)
        self._session_factory = None

        # whether this applet should be enabled
        self._enabled = True

        self._add_custom_routes()

        applets_to_include = API_MODULES.get(self.name_lowercase, {})
        for included_app_name in sorted(applets_to_include):
            try:
                self.include_app(applets_to_include[included_app_name])
            except Exception as e:
                self.log.error(f"Error including app {included_app_name}: {e}")
                self.log.error(traceback.format_exc())

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
        This setup only runs when BBOT server is running natively, e.g. directly connecting to Postgres, Redis, etc.
        """
        # inherit session factory, message queue, etc. from parent applet
        if self.parent is not None:
            self._session_factory = self.parent._session_factory
            self.message_queue = self.parent.message_queue
            self.task_broker = self.parent.task_broker

            # if model isn't defined, inherit from parent
            if self.model is None:
                self.model = self.parent.model

        # taskiq broker
        if self.task_broker is None:
            # taskiq broker
            self.task_broker = await self.message_queue.make_taskiq_broker()
            await self.task_broker.startup()

        # register watchdog tasks
        await self.register_watchdog_tasks(self.task_broker)

        if self.name != "Root Applet":
            try:
                status, reason = await self.setup()
                if not status:
                    self._enabled = False
                if status is None:
                    self.log.warning(f"Setup soft-failed for {self.name}: {reason}")
                elif status is False:
                    self.log.error(f"Error setting up {self.name}: {reason}")
            except Exception as e:
                raise BBOTServerError(f"Error setting up {self.name}: {e}") from e

    async def register_watchdog_tasks(self, broker):
        # register watchdog tasks
        methods = {name: member for name, member in getmembers(self) if callable(member)}
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
                cron = OmegaConf.select(self.global_config, cron_config_key, default=cron_default)
                kwargs["schedule"] = [{"cron": cron}]
            elif cron_default is not None:
                kwargs["schedule"] = [{"cron": cron_default}]
            self.log.debug(f"Registering task: {method_name} {kwargs}")
            task = broker.register_task(method, **kwargs)
            # overwrite the original method with the decorated TaskIQ task
            setattr(self, method_name, task)

    async def setup(self):
        """
        Override this method for any applet-specific setup

        Returns a 2-tuple (status, reason), where status can be either True (success), None (soft-fail), or False (hard-fail)
        """
        return True, ""

    async def _cleanup(self):
        for child_applet in self.child_applets:
            await child_applet.cleanup()
            await child_applet._cleanup()

    async def cleanup(self):
        pass

    async def handle_activity(self, activity: Activity, asset: Asset = None):
        pass

    async def handle_event(self, event: Event, asset=None):
        return []

    def make_activity(self, *args, **kwargs):
        return Activity(*args, **kwargs)

    async def emit_activity(self, *args, **kwargs):
        """
        Emits an activity to the message queue.

        Accepts either an Activity object, or arguments to create a new Activity object.
        """
        if not kwargs and len(args) == 1 and isinstance(args[0], Activity):
            activity = args[0]
        else:
            activity = Activity(*args, **kwargs)
        await self._emit_activity(activity)

    async def _emit_activity(self, activity: Activity):
        self.log.info(f"Emitting activity: {activity.type} - {activity.description}")
        await self.root.message_queue.publish_asset(activity)

    def include_app(self, app_class):
        self.log.debug(f"{self.name_lowercase} including applet {app_class.name_lowercase}")

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

    ### SQLAlchemy convenience methods ###

    def session(self):
        """Get an async session context manager."""
        return self._session_factory()

    async def _get_one(self, **filters):
        """Get a single row matching filters, or None."""
        async with self.session() as session:
            stmt = select(self.model)
            for k, v in filters.items():
                stmt = stmt.where(getattr(self.model, k) == v)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def _insert(self, obj):
        """Insert a new object and return it refreshed."""
        async with self.session() as session:
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return obj

    async def _upsert(self, obj, conflict_columns: list[str]):
        """Insert or update on conflict."""
        from sqlalchemy.dialects.postgresql import insert
        async with self.session() as session:
            values = {
                c.key: getattr(obj, c.key)
                for c in self.model.__table__.columns
                if getattr(obj, c.key, None) is not None
            }
            stmt = insert(self.model).values(**values)
            update_cols = {k: v for k, v in values.items() if k not in conflict_columns}
            stmt = stmt.on_conflict_do_update(index_elements=conflict_columns, set_=update_cols)
            await session.execute(stmt)
            await session.commit()

    async def _update(self, filters: dict, updates: dict):
        """Update rows matching filters. Returns number of rows affected."""
        async with self.session() as session:
            stmt = update(self.model)
            for k, v in filters.items():
                stmt = stmt.where(getattr(self.model, k) == v)
            stmt = stmt.values(**updates)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount

    async def _delete(self, **filters):
        """Delete rows matching filters."""
        async with self.session() as session:
            stmt = sa_delete(self.model)
            for k, v in filters.items():
                stmt = stmt.where(getattr(self.model, k) == v)
            await session.execute(stmt)
            await session.commit()

    class NameLowercaseDescriptor:
        def __init__(self):
            self._cache = {}

        def __get__(self, obj, owner):
            cache_key = owner if obj is None else obj
            if cache_key not in self._cache:
                self._cache[cache_key] = word_regex.sub("_", cache_key.name.lower())
            return self._cache[cache_key]

    name_lowercase = NameLowercaseDescriptor()

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

    async def watches_event(self, event_type):
        if "*" in self.watched_events:
            return True
        return event_type in self.watched_events

    async def watches_activity(self, activity, activity_json):
        if "*" in self.watched_activities:
            return True
        return activity.type in self.watched_activities

    async def compute_stats(self, asset, stats):
        pass

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

            if not hasattr(function, "_endpoint"):
                continue

            try:
                bbot_server_route = make_bbotserver_route(function, tags=[self.tag])
            except BBOTServerValueError:
                continue
            bbot_server_route.add_to_applet(self)

    @property
    def global_config(self):
        return self.root._config

    @property
    def config(self):
        return self.global_config.modules.get(self.name, {})

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
