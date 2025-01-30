import nats
import orjson
import asyncio
from pydantic import BaseModel
from contextlib import suppress

from nats.aio.errors import ErrConnectionClosed, ErrTimeout, ErrNoServers

from .base import BaseMessageQueue


class NATSMessageQueue(BaseMessageQueue):
    """
    docker run --rm -p 4222:4222 nats
    """

    async def setup(self):
        self._active_subscriptions = []

        self.log.info(f"Setting up message queue at {self.uri}")
        while 1:
            try:
                self.nc = await nats.connect(self.uri)
                break
            except Exception as e:
                self.log.error(f"Failed to connect to message queue at {self.uri}: {e}, retrying...")
                await asyncio.sleep(1)

    async def publish(self, message: BaseModel, subject: str):
        msg_bytes = message.model_dump_json().encode()
        await self.nc.publish(subject, msg_bytes)

    async def subscribe(self, callback, subject: str):
        async def wrapped_callback(msg):
            message_json = orjson.loads(msg.data)
            await callback(message_json)

        subscription = await self.nc.subscribe(subject, cb=wrapped_callback)
        self._active_subscriptions.append(subscription)

    async def cleanup(self):
        for sub in self._active_subscriptions:
            with suppress(BaseException):
                await sub.unsubscribe()

        # Close the connection
        with suppress(BaseException):
            await self.nc.close()
        for task_name in (
            "_reading_task",
            "_ping_interval_task",
            "_reconnection_task",
        ):
            task = getattr(self.nc, task_name, None)
            if task:
                with suppress(BaseException):
                    await task
        self.log.info("Connection closed successfully.")
