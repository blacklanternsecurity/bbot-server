import asyncio
import logging
import traceback

from pydantic import BaseModel

from bbot.models.pydantic import Event
from bbot_server.models.activity_models import Activity


class BaseMessageQueue:
    """
    Base class for message queues.
    """

    def __init__(self, uri, config):
        self.log = logging.getLogger(__name__)
        self.uri = uri
        self.config = config

    async def publish_event(self, event: Event):
        """
        Publish a BBOT scan event to the message queue.
        """
        await self.publish(event, "events")

    async def tail_events(self, n: int = 0):
        """
        Tail new events as they come in
        """
        async for event in self.tail(Event, "events", n=n):
            yield event

    async def publish_asset(self, activity: Activity):
        """
        Publish an asset to the message queue.
        """
        await self.publish(activity, "assets")

    async def tail_activities(self, n: int = 0):
        """
        Tail new assets as they come in
        """
        async for activity in self.tail(Activity, "assets", n=n):
            yield activity

    async def tail(self, model: BaseModel, subject: str, n=0):
        q = asyncio.Queue()

        async def callback(msg):
            await q.put(msg)

        try:
            subscription = await self.subscribe(subject, callback, historic=n)
        except Exception as e:
            self.log.critical(f"Error subscribing to {subject}: {e}")
            self.log.critical(traceback.format_exc())
            raise e

        while 1:
            try:
                message = await asyncio.wait_for(q.get(), timeout=0.5)
                yield model(**message)
            except asyncio.TimeoutError:
                continue
            except GeneratorExit:
                raise
            except (asyncio.CancelledError, RuntimeError):
                break
            except BaseException as e:
                self.log.error(f"Error in tail: {e}")
                self.log.error(traceback.format_exc())
                break

        await self.unsubscribe(subscription)

    async def make_taskiq_broker(self):
        """
        Make a taskiq broker for this message queue.
        """
        raise NotImplementedError()

    async def publish(self, message: BaseModel, subject: str):
        """
        Publish a message to the given subject.
        """
        raise NotImplementedError()

    async def setup(self):
        """
        Perform typical setup tasks like instantiating the connection and individual channels.
        """
        raise NotImplementedError()

    async def subscribe(self, subject: str, callback, durable: str = None, historic=0):
        """
        Execute a callback for each new message on the given subject.
        """
        raise NotImplementedError()

    async def cleanup(self):
        """
        Perform cleanup tasks like closing connections and channels.
        """
        raise NotImplementedError()
