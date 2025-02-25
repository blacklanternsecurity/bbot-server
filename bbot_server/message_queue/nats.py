import nats
import orjson
import asyncio
import functools
from pydantic import BaseModel
from contextlib import suppress
from taskiq_nats import NatsBroker

from .base import BaseMessageQueue


class NATSMessageQueue(BaseMessageQueue):
    """
    docker run --rm -p 4222:4222 nats -js
    """

    async def setup(self):
        self._active_subscriptions = []

        base_stream_config = {
            "name": "bbot",
            "subjects": ["bbot.*"],
            "storage": "memory",
            "retention": "limits",
            "max_msgs": 10000,
            "discard": "old",
        }

        self.log.info(f"Setting up message queue at {self.uri}")
        while 1:
            try:
                self.nc = await nats.connect(self.uri)
                self.js = self.nc.jetstream()
                await self.js.add_stream(config=nats.js.api.StreamConfig(**base_stream_config))
                break
            except Exception as e:
                self.log.error(f"Failed to connect to message queue at {self.uri}: {e}, retrying...")
                await asyncio.sleep(1)

    async def make_taskiq_broker(self):
        return NatsBroker(self.uri)

    async def get(self, subject: str, durable: str = None):
        sub = await self.js.pull_subscribe(subject, durable=durable)
        message = await sub.fetch(1)[0]
        if durable:
            await message.ack()
        return orjson.loads(message.data)

    async def publish(self, message, subject: str):
        """
        Publish a message to the message queue.

        Message can be either raw bytes, a Pydantic model, or a dictionary.
        """
        if not isinstance(message, bytes):
            if isinstance(message, BaseModel):
                message = message.model_dump_json().encode()
            else:
                message = orjson.dumps(message)
        await self.js.publish(subject, message)

    async def subscribe(self, callback, subject: str, durable: str = None):
        @functools.wraps(callback)
        async def wrapped_callback(msg):
            message_json = orjson.loads(msg.data)
            await callback(message_json)

        kwargs = {}
        if durable is not None:
            kwargs["durable"] = durable
            kwargs["config"] = nats.js.api.ConsumerConfig(ack_policy="explicit")

        try:
            subscription = await self.js.subscribe(subject, cb=wrapped_callback, **kwargs)
        except Exception as e:
            self.log.error(f"Failed to subscribe to {subject}: {e}")
            raise

        self._active_subscriptions.append(subscription)
        return subscription

    async def unsubscribe(self, subscription):
        await subscription.unsubscribe()

    async def clear(self):
        await self.js.purge_stream("bbot")

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
