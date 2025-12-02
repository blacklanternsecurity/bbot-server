import asyncio
import logging
import traceback
from contextlib import suppress

import httpx
from taskiq.schedule_sources import LabelScheduleSource
from taskiq.api import run_receiver_task, run_scheduler_task
from taskiq import TaskiqScheduler, TaskiqEvents, TaskiqState

from bbot_server.modules import Asset
from bbot.models.pydantic import Event
from bbot_server.errors import BBOTServerNotFoundError
from bbot_server.modules.activity.activity_models import Activity


class BBOTWatchdog:
    """
    Contains:
        - taskiq worker
        - taskiq scheduler
        - event queue listener
    """

    def __init__(self, bbot_server, http_client: httpx.AsyncClient | None = None):
        self.log = logging.getLogger(__name__)
        # bbot server
        self.bbot_server = bbot_server
        self._http_client = http_client
        self._owns_http_client = http_client is None
        self._alert_webhook_url = ""
        self._alerts_enabled = False
        self._last_alert_client_verify = None
        self._load_alert_config()

    async def start(self) -> None:
        self._load_alert_config()
        self.broker = await self.bbot_server.message_queue.make_taskiq_broker()
        self.broker.is_worker_process = True

        # attach bbot_server to the taskiq broker state
        async def startup(state: TaskiqState) -> None:
            state.bbot_server = self.bbot_server

        self.broker.add_event_handler(TaskiqEvents.WORKER_STARTUP, startup)
        # taskiq scheduler
        self.taskiq_schedule_source = LabelScheduleSource(self.broker)
        self.taskiq_scheduler = TaskiqScheduler(self.broker, [self.taskiq_schedule_source])

        if self._alerts_enabled and self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=10, verify=False)

        await self.broker.startup()

        # register watchdog tasks
        for app in self.bbot_server.all_child_applets(include_self=True):
            await app.register_watchdog_tasks(self.broker)

        # taskiq worker tasks
        self.taskiq_worker_task = asyncio.create_task(run_receiver_task(self.broker))
        self.taskiq_scheduler_task = asyncio.create_task(run_scheduler_task(self.taskiq_scheduler))

        # listen for new events
        self.event_listener = await self.bbot_server.message_queue.subscribe(
            "events", self._event_listener, durable="bbot_worker"
        )
        # listen for new activities
        self.activity_listener = await self.bbot_server.message_queue.subscribe(
            "assets", self._activity_listener, durable="bbot_worker"
        )

    async def _event_listener(self, message: dict) -> None:
        """
        Consume events from the queue and distribute them to the applets
        """
        try:
            activities = []
            event = Event(**message)
            event_data = getattr(event, "data", None)
            event_host = getattr(event, "host", None)
            if event_data:
                event_preview = f": {event_data}"
            elif event_host:
                event_preview = f": {event_host}"
            else:
                event_preview = ""
            self.log.info(f"Received event: {event.type}{event_preview}")
            await self._send_event_alert(event)
            # get the event's associated asset (this saves on database queries since it will be passed down to each applet)
            asset, _activities = await self._get_or_create_asset(event.host, event=event)
            activities.extend(_activities)

            # let each applet process the event
            for applet in self.bbot_server.all_child_applets(include_self=True):
                if not applet._enabled:
                    continue
                if await applet.watches_event(event.type):
                    try:
                        _activities = await applet.handle_event(event, asset) or []
                        activities.extend(_activities)
                    except Exception as e:
                        self.log.error(f"Error ingesting event {event.type} for applet {applet.name}: {e}")
                        self.log.error(traceback.format_exc())

            # update the asset in the database
            if activities and asset is not None:
                await self.bbot_server.assets.update_asset(asset)

            # publish applet activities to the message queue
            for activity in activities:
                await self.bbot_server._emit_activity(activity)

        except Exception as e:
            self.log.error(f"Error ingesting event {event.type}: {e}")
            self.log.error(traceback.format_exc())

    def _load_alert_config(self) -> None:
        """Load webhook alert configuration from the BBOT server config."""

        try:
            watchdog_config = self.bbot_server.config.get("watchdog", {}) or {}
            alerts_config = watchdog_config.get("alerts", {}) or {}
        except Exception:
            alerts_config = {}

        webhook_url = alerts_config.get("webhook_url", "") or ""
        self._alert_webhook_url = webhook_url.strip()
        self._alerts_enabled = bool(alerts_config.get("enabled", False) or self._alert_webhook_url)

    async def _send_event_alert(self, event: Event) -> None:
        """Send a webhook notification when a new event is identified."""

        if not (self._alerts_enabled and self._alert_webhook_url and self._http_client):
            return

        payload = {
            "summary": f"New event detected: {event.type}"
            + (f" on {event.host}" if getattr(event, "host", None) else ""),
            "event": event.model_dump(mode="json"),
        }

        client = self._http_client
        owns_temp_client = False

        if not self._owns_http_client:
            transport = getattr(client, "_transport", None)
            client = httpx.AsyncClient(timeout=10, verify=False, transport=transport)
            owns_temp_client = True

        self._last_alert_client_verify = False

        try:
            response = await client.post(self._alert_webhook_url, json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            self.log.error(f"Error sending webhook alert to {self._alert_webhook_url}: {exc}")
        finally:
            if owns_temp_client:
                await client.aclose()

    async def _activity_listener(self, message: dict) -> None:
        """
        Consume activities from the queue and distribute them to the applets
        """
        activity = Activity(**message)
        activity_json = activity.model_dump()
        activities = []
        asset, _activities = await self._get_or_create_asset(activity.host, parent_activity=activity)
        activities.extend(_activities)

        # let each applet process the activity
        for applet in self.bbot_server.all_child_applets(include_self=True):
            if await applet.watches_activity(activity, activity_json):
                try:
                    _activities = await applet.handle_activity(activity, asset) or []
                    activities.extend(_activities)
                except Exception as e:
                    self.log.error(f"Error processing activity {activity.type} for applet {applet.name}: {e}")
                    self.log.error(traceback.format_exc())

        # publish new activities to the message queue
        for activity in activities:
            await self.bbot_server._emit_activity(activity)

        # update the asset in the database
        if activities and asset is not None:
            await self.bbot_server.assets.update_asset(asset)

    async def _get_or_create_asset(self, host: str, event: Event = None, parent_activity: Activity = None) -> Asset:
        """
        Given a host, get the asset from the database. If it doesn't exist, create it.

        Returns the asset and a list of activities that were generated (NEW_ASSET if the asset was created).
        """
        if not host:
            return None, []
        activities = []
        try:
            asset = await self.bbot_server.assets.get_asset(host)
        except BBOTServerNotFoundError:
            asset = Asset(host=host)
            activities = [
                self.bbot_server.assets.make_activity(
                    type="NEW_ASSET",
                    description=f"New asset: [[COLOR]{host}[/COLOR]]",
                    event=event,
                    parent_activity=parent_activity,
                )
            ]
        return asset, activities

    async def stop(self) -> None:
        self.log.info("Stopping watchdog")
        if self._owns_http_client and self._http_client is not None:
            await self._http_client.aclose()
        await self.bbot_server.message_queue.unsubscribe(self.event_listener)
        self.taskiq_worker_task.cancel()
        self.taskiq_scheduler_task.cancel()
        with suppress(asyncio.CancelledError):
            await self.taskiq_worker_task
            await self.taskiq_scheduler_task
        await self.broker.shutdown()
        await self.bbot_server.cleanup()
