import orjson
import asyncio
import traceback
from contextlib import suppress

import redis.asyncio as redis
from taskiq_redis import RedisStreamBroker

from .base import BaseMessageQueue
from bbot_server.utils.misc import smart_encode
from bbot_server.utils.async_utils import async_to_sync_class


class Subscription:
    def __init__(self, subject, task):
        self.subject = subject
        self.task = task

    async def unsubscribe(self):
        self.task.cancel()
        with suppress(asyncio.CancelledError):
            await self.task


@async_to_sync_class
class RedisMessageQueue(BaseMessageQueue):
    """
    A wrapper around Redis, which uses two different key patterns:
    - bbot:stream:{subject}: for persistent, tailable streams - e.g. events, activities
    - bbot:work:{subject}: for one-time messages, e.g. tasks

    docker run --rm -p 6379:6379 redis
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._active_subscriptions = []

    async def setup(self):
        self.log.debug(f"Setting up Redis message queue at {self.uri}")

        while True:
            try:
                self.redis = redis.from_url(self.uri)
                await self.redis.ping()
                break
            except Exception as e:
                self.log.error(f"Failed to connect to Redis at {self.uri}: {e}, retrying...")
                await asyncio.sleep(1)

    async def make_taskiq_broker(self):
        return RedisStreamBroker(self.uri)

    async def get(self, subject: str, timeout=None):
        subject = f"bbot:work:{subject}"

        try:
            if timeout is not None:
                result = await self.redis.blpop(subject, timeout=timeout)
                if result is None:
                    raise TimeoutError(f"Timed out waiting for message from {subject}")
                _, data = result
            else:
                data = await self.redis.lpop(subject)
                if data is None:
                    return None

            return orjson.loads(data)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Failed to fetch message from {subject}")

    async def put(self, message, subject: str):
        subject = f"bbot:work:{subject}"
        message = smart_encode(message)
        await self.redis.rpush(subject, message)

    async def publish(self, message, subject: str):
        stream_key = f"bbot:stream:{subject}"
        message_data = smart_encode(message)
        await self.redis.xadd(stream_key, {"data": message_data}, maxlen=10000, approximate=True)

    async def subscribe(self, subject: str, callback, durable: str = None, historic=0):
        if not callable(callback):
            raise ValueError("Callback must be a callable")
        if not isinstance(subject, str):
            raise ValueError("Subject must be a string")

        stream_key = f"bbot:stream:{subject}"
        if historic > 0:
            messages = await self.redis.xrevrange(stream_key, count=historic)
            await self._callback(callback, *messages[::-1])

        # Create consumer name and group name as strings (not bytes)
        consumer_name = f"{durable}-{id(callback)}" if durable else f"ephemeral-{id(callback)}"
        group_name = durable if durable else f"ephemeral-{id(callback)}"

        # Create a task to process messages
        async def message_handler():
            self.log.info(f"Subscribed to {stream_key}")
            while True:
                try:
                    # Read new messages from the stream
                    streams = await self.redis.xreadgroup(
                        group_name, consumer_name, {stream_key: ">"}, count=10, block=1000
                    )
                    if streams:
                        for stream_name, messages in streams:
                            if durable:
                                for message_id, _ in messages:
                                    await self.redis.xack(stream_key, group_name, message_id)
                            await self._callback(callback, *messages)
                except redis.ResponseError as e:
                    self.log.debug(f"Error reading from stream {stream_key}: {e}")
                    if "NOGROUP" in str(e):
                        try:
                            # For non-durable subscribers, start from '$' (only new messages)
                            # For durable subscribers, start from '0' (all messages)
                            start_id = "0" if durable else "$"
                            await self.redis.xgroup_create(stream_key, group_name, id=start_id, mkstream=True)
                        except redis.ResponseError as create_err:
                            self.log.error(f"Failed to recreate group: {create_err}")
                            # if "BUSYGROUP" not in str(create_err):
                            #     self.log.error(f"Failed to recreate group: {create_err}")                    else:
                        self.log.debug("Sleeping for .1 seconds")
                    await asyncio.sleep(0.1)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.log.error(f"Error in message handler: {e}")
                    await asyncio.sleep(1)

        # Start the message handler task
        task = asyncio.create_task(message_handler())

        subscription = Subscription(stream_key, task)
        self._active_subscriptions.append(subscription)
        return subscription

    async def unsubscribe(self, subscription):
        with suppress(Exception):
            await subscription.unsubscribe()
            if subscription in self._active_subscriptions:
                self._active_subscriptions.remove(subscription)

    async def clear(self):
        stream_keys = await self.redis.keys("bbot:stream:*")
        work_keys = await self.redis.keys("bbot:work:*")

        if stream_keys:
            await self.redis.delete(*stream_keys)
        if work_keys:
            await self.redis.delete(*work_keys)

    async def cleanup(self):
        for subscription in self._active_subscriptions:
            await self.unsubscribe(subscription)
        self._active_subscriptions = []

        if hasattr(self, "redis") and self.redis:
            await self.redis.aclose()

    async def _callback(self, callback, *messages):
        """
        Given a bunch of redis messages, call the callback with each message
        """
        for message_id, message in messages:
            message = message.get(b"data") or message.get("data")
            message = orjson.loads(message)
            try:
                await callback(message)
            except Exception as e:
                self.log.error(f"Error in callback {callback.__name__}({message}): {e}")
                self.log.error(traceback.format_exc())
