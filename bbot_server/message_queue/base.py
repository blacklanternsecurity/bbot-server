import asyncio
import logging
import traceback

from pydantic import BaseModel

from bbot.models.pydantic import Event
from bbot_server.models.assets import AssetActivity


class BaseMessageQueue:
    """
    Base class for message queues.
    """

    def __init__(self, uri, config):
        self.log = logging.getLogger(__name__)
        self.uri = uri
        self.config = config

    async def event_publish(self, event: Event):
        """
        Publish a BBOT scan event to the message queue.
        """
        await self.publish(event, "bbot.events")

    async def event_tail(self):
        """
        Tail new events as they come in
        """
        async for event in self.tail(Event, "bbot.events"):
            yield event

    async def asset_publish(self, activity: AssetActivity):
        """
        Publish an asset to the message queue.
        """
        await self.publish(activity, "bbot.assets")

    async def asset_tail(self):
        """
        Tail new assets as they come in
        """
        async for activity in self.tail(AssetActivity, "bbot.assets"):
            yield activity

    async def tail(self, model: BaseModel, subject: str):
        q = asyncio.Queue()

        async def callback(msg):
            await q.put(msg)

        await self.subscribe(callback, subject)

        while 1:
            try:
                message = await asyncio.wait_for(q.get(), timeout=30)
                yield model(**message)
            except asyncio.TimeoutError:
                continue
            except (asyncio.CancelledError, RuntimeError):
                break
            except BaseException as e:
                self.log.error(f"Error in tail: {e}")
                self.log.error(traceback.format_exc())
                break

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

    async def subscribe(self, callback, subject: str):
        """
        Execute a callback for each new message on the given subject.
        """
        raise NotImplementedError()

    async def cleanup(self):
        """
        Perform cleanup tasks like closing connections and channels.
        """
        raise NotImplementedError()
