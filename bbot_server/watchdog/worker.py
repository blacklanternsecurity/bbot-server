import asyncio
import logging
import traceback
from contextlib import suppress
from taskiq.schedule_sources import LabelScheduleSource
from taskiq import TaskiqScheduler, TaskiqEvents, TaskiqState

from bbot.models.pydantic import Event

from taskiq.api import run_receiver_task, run_scheduler_task


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
        self.broker = None

    async def start(self) -> None:
        await self.bbot_server.setup()

        self.broker = self.bbot_server.task_broker
        self.broker.is_worker_process = True

        # attach bbot_server to the taskiq broker state
        async def startup(state: TaskiqState) -> None:
            state.bbot_server = self.bbot_server

        self.broker.add_event_handler(TaskiqEvents.WORKER_STARTUP, startup)
        # taskiq scheduler
        self.taskiq_scheduler = TaskiqScheduler(self.broker, [LabelScheduleSource(self.broker)])

        await self.bbot_server.register_watchdog_tasks(self.broker)

        # taskiq worker tasks
        self.taskiq_worker_task = asyncio.create_task(run_receiver_task(self.broker))
        self.taskiq_scheduler_task = asyncio.create_task(run_scheduler_task(self.taskiq_scheduler))

        # start the event queue listener
        self.event_listener = await self.bbot_server.message_queue.subscribe(
            self._event_listener, "bbot.events", durable="events_watchdog"
        )

    async def _event_listener(self, message: dict) -> None:
        """
        Consume events from the event queue and insert them into the database
        """
        activities = []
        event = Event(**message)
        # write the event to the database
        await self.bbot_server.event_store.insert_event(event)
        # let each applet process the event
        for applet in self.bbot_server.all_child_applets:
            if event.type in applet.watched_events:
                try:
                    activities.extend(await applet.ingest_event(event))
                except Exception as e:
                    self.log.error(f"Error ingesting event {event.type} for applet {applet.name}: {e}")
                    self.log.error(traceback.format_exc())
        # publish applet activities to the message queue
        for activity in activities:
            await self.bbot_server._emit_activity(activity)

    async def stop(self) -> None:
        await self.bbot_server.message_queue.unsubscribe(self.event_listener)
        self.taskiq_worker_task.cancel()
        self.taskiq_scheduler_task.cancel()
        with suppress(asyncio.CancelledError):
            await self.taskiq_worker_task
            await self.taskiq_scheduler_task
        await self.broker.shutdown()
        await self.bbot_server.cleanup()
