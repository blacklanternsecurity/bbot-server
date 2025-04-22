import asyncio
import logging
import traceback
from contextlib import suppress
from taskiq.schedule_sources import LabelScheduleSource
from taskiq.api import run_receiver_task, run_scheduler_task
from taskiq import TaskiqScheduler, TaskiqEvents, TaskiqState

from bbot.models.pydantic import Event
from bbot_server.errors import BBOTServerNotFoundError
from bbot_server.models.activity_models import Activity


class BBOTWatchdog:
    """
    Contains:
        - taskiq worker
        - taskiq scheduler
        - event queue listener
    """

    def __init__(self, bbot_server):
        self.log = logging.getLogger(__name__)
        # bbot server
        self.bbot_server = bbot_server

    async def start(self) -> None:
        self.broker = await self.bbot_server.message_queue.make_taskiq_broker()
        self.broker.is_worker_process = True

        # attach bbot_server to the taskiq broker state
        async def startup(state: TaskiqState) -> None:
            state.bbot_server = self.bbot_server

        self.broker.add_event_handler(TaskiqEvents.WORKER_STARTUP, startup)
        # taskiq scheduler
        self.taskiq_schedule_source = LabelScheduleSource(self.broker)
        self.taskiq_scheduler = TaskiqScheduler(self.broker, [self.taskiq_schedule_source])

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
            # get the event's associated asset (this saves on database queries since it will be passed down to each applet)
            if event.host is not None:
                try:
                    asset = await self.bbot_server.assets.get_asset(event.host)
                except BBOTServerNotFoundError:
                    asset = self.bbot_server.assets.model(host=event.host)
                    activity = self.bbot_server.assets.make_activity(
                        type="NEW_ASSET",
                        description=f"New asset: [[COLOR]{event.host}[/COLOR]]",
                        event=event,
                    )
                    activities.append(activity)
            else:
                asset = None

            # let each applet process the event
            for applet in self.bbot_server.all_child_applets(include_self=True):
                if applet.watches_event(event.type):
                    try:
                        new_activities = await applet.handle_event(event, asset) or []
                        activities.extend(new_activities)
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

    async def _activity_listener(self, message: dict) -> None:
        """
        Consume activities from the queue and distribute them to the applets
        """
        activity = Activity(**message)
        new_activites = []
        # let each applet process the activity
        for applet in self.bbot_server.all_child_applets(include_self=True):
            if applet.watches_activity(activity.type):
                try:
                    new_activities = await applet.handle_activity(activity) or []
                    new_activites.extend(new_activities)

                    # publish new activities to the message queue
                    for activity in new_activities:
                        await self.bbot_server._emit_activity(activity)
                except Exception as e:
                    self.log.error(f"Error processing activity {activity.type} for applet {applet.name}: {e}")
                    self.log.error(traceback.format_exc())

    async def stop(self) -> None:
        self.log.info("Stopping watchdog")
        await self.bbot_server.message_queue.unsubscribe(self.event_listener)
        self.taskiq_worker_task.cancel()
        self.taskiq_scheduler_task.cancel()
        with suppress(asyncio.CancelledError):
            await self.taskiq_worker_task
            await self.taskiq_scheduler_task
        await self.broker.shutdown()
        await self.bbot_server.cleanup()
