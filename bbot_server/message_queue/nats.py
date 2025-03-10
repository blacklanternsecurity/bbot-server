import nats
import orjson
import asyncio
import functools
import traceback
from pydantic import BaseModel
from contextlib import suppress
from taskiq_nats import NatsBroker

from .base import BaseMessageQueue

from bbot_server.utils.misc import smart_encode
from bbot_server.errors import BBOTServerValueError


class NATSMessageQueue(BaseMessageQueue):
    """
    docker run --rm -p 4222:4222 nats -js

    A wrapper around NATS, which uses two different streams:
    - bbot_stream: for persistent, tailable queues - e.g. events, activities
    - bbot_work: for one-time messages, e.g. tasks

    .publish()/subscribe() are used for persistent queues, which can grow in size up to max_msgs.
    These can be tailed/consumed at any time by multiple consumers.

    .get()/.put() are used for one-off messages, which are deleted after consumption.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._consumers = {}  # Store consumers by subject

    async def setup(self):
        self._active_subscriptions = []

        # stream config - for persistent, tailable queues
        base_stream_config = {
            "name": "bbot_stream",
            "subjects": ["bbot.stream.*"],
            "storage": "memory",
            "retention": "limits",
            "max_msgs": 10000,
        }
        # work config - for one-time messages
        base_work_config = {
            "name": "bbot_work",
            "subjects": ["bbot.work.*"],
            "storage": "memory",
            "retention": "workqueue",
            "max_msgs": 10000,
        }

        self.log.info(f"Setting up message queue at {self.uri}")

        while 1:
            try:
                self.nc = await nats.connect(self.uri)
                self.js = self.nc.jetstream()
                break
            except Exception as e:
                self.log.error(f"Failed to connect to message queue at {self.uri}: {e}, retrying...")
                self.log.error(traceback.format_exc())
                await asyncio.sleep(1)

        for config in [base_stream_config, base_work_config]:
            while 1:
                try:
                    await self.js.add_stream(config=nats.js.api.StreamConfig(**config))
                    break
                except Exception as e:
                    self.log.error(f"Failed to add stream {config['name']} at {self.uri}: {e}, retrying...")
                    self.log.error(traceback.format_exc())
                    await asyncio.sleep(1)

    async def make_taskiq_broker(self):
        return NatsBroker(self.uri)

    async def get(self, subject: str, timeout=None):
        subject = f"bbot.work.{subject}"

        try:
            consumer = await self.js.pull_subscribe(
                subject,
                durable=subject.replace(".", "_"),  # Use durable consumer
                stream="bbot_work",
            )
            messages = await consumer.fetch(batch=1, timeout=timeout)
            if messages:
                message = messages[0]
                await message.ack()
                return orjson.loads(message.data)
            return None
        except nats.errors.TimeoutError as e:
            raise TimeoutError(f"Failed to fetch message from {subject}: {e}")

    async def put(self, message, subject: str):
        subject = f"bbot.work.{subject}"
        message = smart_encode(message)
        await self.js.publish(subject, message, stream="bbot_work")

    async def publish(self, message, subject: str):
        """
        Publish a message to the message queue.

        Message can be either raw bytes, a Pydantic model, or a dictionary.
        """
        subject = f"bbot.stream.{subject}"
        message = smart_encode(message)
        await self.js.publish(subject, message, stream="bbot_stream")

    async def subscribe(self, callback, subject: str, durable: str = None):
        subject = f"bbot.stream.{subject}"

        @functools.wraps(callback)
        async def wrapped_callback(msg):
            message_json = orjson.loads(msg.data)
            await callback(message_json)

        config = None
        if durable:
            config = nats.js.api.ConsumerConfig(
                durable_name=durable,
            )

        subscription = await self.js.subscribe(subject, cb=wrapped_callback, stream="bbot_stream", config=config)

        self._active_subscriptions.append(subscription)
        return subscription

    async def unsubscribe(self, subscription):
        with suppress(Exception):
            await subscription.unsubscribe()

    async def clear(self):
        for stream in ["bbot_stream", "bbot_work"]:
            await self.js.purge_stream(stream)

    async def cleanup(self):
        # Add consumer cleanup
        for consumer in self._consumers.values():
            with suppress(Exception):
                await consumer.unsubscribe()
        self._consumers.clear()

        # Close the connection
        with suppress(Exception):
            await self.nc.close()
        for task_name in (
            "_reading_task",
            "_ping_interval_task",
            "_reconnection_task",
        ):
            task = getattr(self.nc, task_name, None)
            if task:
                task.cancel()
                with suppress(BaseException):
                    await task
        self.log.info("Connection closed successfully.")
