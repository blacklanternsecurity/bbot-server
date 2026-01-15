import re
import asyncio
import inspect
import logging
import traceback
from fastapi import APIRouter
from omegaconf import OmegaConf
from typing import Annotated, Any  # noqa
from functools import cached_property
from pydantic import BaseModel, Field  # noqa
from pymongo import WriteConcern
from pymongo.errors import OperationFailure, DuplicateKeyError

from bbot_server.assets import Asset
from bbot.models.pydantic import Event
from bbot_server.modules import API_MODULES
from bbot.core.helpers import misc as bbot_misc
from bbot_server.utils import misc as bbot_server_misc
from bbot_server.utils.db import (
    desired_indexes_from_model,
    parse_existing_indexes,
    compute_index_diff,
    merge_desired_indexes,
)
from bbot_server.applets._routing import make_bbotserver_route
from bbot_server.modules.activity.activity_models import Activity
from bbot_server.errors import BBOTServerError, BBOTServerValueError
from bbot_server.utils.misc import _sanitize_mongo_query, _sanitize_mongo_aggregation

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

        # whether this applet should be enabled
        self._enabled = True

        # mongo stuff
        self.collection = None
        self.strict_collection = None

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
        This setup only runs when BBOT server is running natively, e.g. directly connecting to mongo, redis, etc.
        """
        # inherit config, db, message queue, etc. from parent applet
        if self.parent is not None:
            self.asset_store = self.parent.asset_store
            self.user_store = self.parent.user_store
            self.event_store = self.parent.event_store
            self.message_queue = self.parent.message_queue
            self.task_broker = self.parent.task_broker

            # if model isn't defined, inherit collection from parent
            if self.model is None:
                self.model = self.parent.model
                self.db = self.parent.db
                self.collection = self.parent.collection
                self.strict_collection = self.parent.strict_collection
            else:
                # otherwise, set up applet-specific db tables
                self.table_name = getattr(self.model, "__table_name__", None)
                self.store_type = getattr(self.model, "__store_type__", None)
                if self.store_type not in ("user", "asset", "event"):
                    raise BBOTServerValueError(
                        f"Invalid store type: {self.store_type} on model {self.model.__name__} - must be one of: user, asset, event"
                    )
                if self.store_type == "user":
                    self.db = self.user_store.db
                elif self.store_type == "asset":
                    self.db = self.asset_store.db
                elif self.store_type == "event":
                    self.db = self.event_store.db

                # if this applet doesn't have its own table, inherit from parent
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

                # index building is deferred to reconcile_all_indexes()

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

    async def reconcile_all_indexes(self):
        """
        Reconcile indexes for all collections used by this applet and its children.

        This aggregates desired indexes from all models that share a collection,
        then applies a single diff per collection.
        """
        # Group applets by collection
        applets_by_collection = {}
        for applet in self.all_child_applets(include_self=True):
            if applet.collection is None or applet.model is None:
                continue
            collection_name = applet.collection.full_name
            if collection_name not in applets_by_collection:
                applets_by_collection[collection_name] = {"collection": applet.collection, "models": []}
            applets_by_collection[collection_name]["models"].append(applet.model)

        # Reconcile each collection
        for collection_name, data in applets_by_collection.items():
            collection = data["collection"]
            models = data["models"]

            # Merge desired indexes from all models
            all_desired = [desired_indexes_from_model(m) for m in models]
            desired, desired_text = merge_desired_indexes(all_desired)

            # Get existing indexes
            indexes_cursor = await collection.list_indexes()
            indexes_list = [idx async for idx in indexes_cursor]
            existing, existing_text = parse_existing_indexes(indexes_list)

            # Compute and apply diff
            diff = compute_index_diff(desired, desired_text, existing, existing_text)
            await self._apply_index_diff(collection, diff, existing)

    async def _apply_index_diff(self, collection, diff, existing):
        """Apply index diff to a collection."""
        # Apply text index changes
        if diff["drop_text"]:
            text_idx_name = next((n for n, s in existing.items() if s.get("text")), None)
            if text_idx_name:
                self.log.debug(f"Dropping text index {text_idx_name}")
                await collection.drop_index(text_idx_name)
        if diff["create_text"]:
            key = [(f, "text") for f in diff["create_text"]]
            self.log.debug(f"Creating text index: {key}")
            await collection.create_index(key)

        # Drop indexes
        for name in diff["drop"]:
            self.log.debug(f"Dropping index {name}")
            await collection.drop_index(name)

        # Create indexes
        for spec in diff["create"]:
            self.log.debug(f"Creating index {spec['name']}: {spec['key']}")
            try:
                await collection.create_index(spec["key"], unique=spec["unique"], sparse=spec["sparse"])
            except DuplicateKeyError as e:
                self.log.error(f"Cannot create unique index {spec['name']}: duplicate values exist. {e}")
            except OperationFailure as e:
                if "already exists" in str(e):
                    self.log.debug(f"Index {spec['name']} already exists")
                else:
                    raise

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

    async def make_bbot_query(
        self,
        query: dict = None,
        search: str = None,
        host: str = None,
        domain: str = None,
        type: str = None,
        target_id: str = None,
        archived: bool = False,
        active: bool = True,
        min_timestamp: float = None,
        max_timestamp: float = None,
        min_created_timestamp: float = None,
        max_created_timestamp: float = None,
        min_modified_timestamp: float = None,
        max_modified_timestamp: float = None,
    ):
        """
        Streamlines querying of a Mongo collection with BBOT-specific filters like "host", "reverse_host", etc.

        This is meant to be a base method with only query logic common to all collections in BBOT server.

        For any additional custom logic like different default kwarg values, etc., override this method on applet-by-applet basis.

        Example:
            async def make_bbot_query(self, type: str = "Asset", query: dict = None, ignored: bool = False, **kwargs):
                query = dict(query or {})
                if ignored is not None and "ignored" not in query:
                    query["ignored"] = ignored
                return await super().make_bbot_query(type=type, query=query, **kwargs)
        """
        query = dict(query or {})
        # AI is dumb and likes to pass in blank strings for stuff
        domain = domain or None
        target_id = target_id or None
        type = type or None
        host = host or None

        if ("type" not in query) and (type is not None):
            query["type"] = type
        if ("host" not in query) and (host is not None):
            query["host"] = host
        if ("reverse_host" not in query) and (domain is not None):
            reversed_host = re.escape(domain[::-1])
            # Match exact domain or subdomains (with dot separator)
            query["reverse_host"] = {"$regex": f"^{reversed_host}(\\.|$)"}

        # timestamps
        if "timestamp" not in query and (min_timestamp is not None or max_timestamp is not None):
            query["timestamp"] = {}
            if min_timestamp is not None:
                query["timestamp"]["$gte"] = min_timestamp
            if max_timestamp is not None:
                query["timestamp"]["$lte"] = max_timestamp

        # created timestamps
        if "created" not in query and (min_created_timestamp is not None or max_created_timestamp is not None):
            query["created"] = {}
            if min_created_timestamp is not None:
                query["created"]["$gte"] = min_created_timestamp
            if max_created_timestamp is not None:
                query["created"]["$lte"] = max_created_timestamp

        # modified timestamps
        if "modified" not in query and (min_modified_timestamp is not None or max_modified_timestamp is not None):
            query["modified"] = {}
            if min_modified_timestamp is not None:
                query["modified"]["$gte"] = min_modified_timestamp
            if max_modified_timestamp is not None:
                query["modified"]["$lte"] = max_modified_timestamp

        if ("scope" not in query) and (target_id is not None):
            target_query_kwargs = {}
            if target_id != "DEFAULT":
                target_query_kwargs["id"] = target_id
            target = await self.root.targets._get_target(**target_query_kwargs, fields=["id"])
            query["scope"] = target["id"]

        # if both active and archived are true, we don't need to filter anything, because we are returning all assets
        if not (active and archived) and ("archived" not in query):
            # if both are false, we need to raise an error
            if not (active or archived):
                raise BBOTServerValueError("Must query at least one of active or archived")
            # only one should be true
            query["archived"] = {"$eq": archived}

        if search:
            search_query = await self.make_search_query(search)
            if search_query:
                query = {"$and": [query, search_query]}

        return _sanitize_mongo_query(query)

    async def make_search_query(self, search: str):
        """
        Given a search term, construct a human-friendly search against multiple fields.
        """
        search_str = search.strip().lower()
        if not search_str:
            return None
        search_str_escaped = re.escape(search_str)
        return {
            "$or": [
                {"$text": {"$search": search_str}},
                {"host_parts": {"$regex": f"^{search_str_escaped}"}},
                {"host": {"$regex": f"^{search_str_escaped}"}},
                {"reverse_host": {"$regex": f"^{re.escape(search_str[::-1])}"}},
            ]
        }

    async def mongo_iter(self, *args, **kwargs):
        """
        Lazy iterator over a Mongo collection with BBOT-specific filters and aggregation
        """
        cursor = await self._make_mongo_cursor(*args, **kwargs)
        async for asset in cursor:
            yield asset

    async def mongo_count(self, *args, **kwargs):
        query = await self.make_bbot_query(*args, **kwargs)
        return await self.collection.count_documents(query)

    async def _make_mongo_cursor(
        self,
        query: dict = None,
        aggregate: list[dict] = None,
        sort: list[str | tuple[str, int]] = None,
        fields: list[str] = None,
        skip: int = None,
        limit: int = None,
        collection=None,
        **kwargs,
    ):
        query = await self.make_bbot_query(query=query, **kwargs)
        fields = {f: 1 for f in fields} if fields else None

        # collection defaults to self.collection
        if collection is None:
            collection = self.collection

        # if we don't have a default collection and none was passed in, raise an error
        if collection is None:
            raise BBOTServerError(f"Collection is not set for {self.name}")

        self.log.info(f"Querying {collection.name}: query={query}, fields={fields}")

        if aggregate:
            # sanitize aggregation pipeline
            aggregate = _sanitize_mongo_aggregation(aggregate)
            aggregate_pipeline = [{"$match": query}] + aggregate
            if limit is not None:
                aggregate_pipeline.append({"$limit": limit})
            self.log.info(f"Querying {collection.name}: aggregate={aggregate_pipeline}")
            cursor = await collection.aggregate(aggregate_pipeline)
        else:
            cursor = collection.find(query, fields)
            if sort:
                processed_sort = []
                for field in sort:
                    if isinstance(field, str):
                        processed_sort.append((field.lstrip("+-"), -1 if field.startswith("-") else 1))
                    else:
                        # assume it's already a tuple (field, direction)
                        processed_sort.append(tuple(field))
                cursor = cursor.sort(processed_sort)

            if limit is not None:
                cursor = cursor.limit(limit)
            if skip is not None:
                cursor = cursor.skip(skip)

        return cursor

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
