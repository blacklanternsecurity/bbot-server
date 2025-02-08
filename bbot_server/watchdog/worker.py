import asyncio
import logging
import traceback
from contextlib import suppress

from bbot.models.pydantic import Event

# from redis.asyncio import ConnectionPool
from taskiq_nats import NatsBroker
from taskiq import TaskiqScheduler
from taskiq.api import run_receiver_task, run_scheduler_task
from taskiq.schedule_sources import LabelScheduleSource

from taskiq import Context, TaskiqDepends, TaskiqEvents, TaskiqState


class WatchdogWorker:
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

        # # register tasks
        # for watchdog_task in self.bbot_server.all_watchdog_tasks:
        #     self.broker.register_task(watchdog_task)

    async def start(self) -> None:
        await self.bbot_server.setup()

        # taskiq broker
        self.taskiq_broker = await self.bbot_server.message_queue.make_taskiq_broker()
        # taskiq scheduler
        self.taskiq_scheduler = TaskiqScheduler(self.taskiq_broker, [LabelScheduleSource(self.taskiq_broker)])
        await self.taskiq_broker.startup()
        # taskiq worker
        self.taskiq_worker = asyncio.create_task(run_receiver_task(self.taskiq_broker))

        # start the event queue listener
        await self.bbot_server.message_queue.subscribe(self._event_listener, "bbot.events")

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
            await self.bbot_server.emit_activity(activity)

    async def stop(self) -> None:
        self.taskiq_worker.cancel()
        with suppress(asyncio.CancelledError):
            await self.taskiq_worker
        await self.taskiq_broker.shutdown()
        await self.bbot_server.cleanup()
