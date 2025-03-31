import asyncio
import functools
import traceback
import orjson
from contextlib import suppress
from typing import Any, Dict, List, Optional, Callable

import redis.asyncio as redis
from taskiq_redis import RedisStreamBroker

from .base import BaseMessageQueue
from bbot_server.utils.misc import smart_encode
from bbot_server.utils.async_utils import async_to_sync_class


class Subscription:
    def __init__(self, subject, pubsub, task):
        self.subject = subject
        self.pubsub = pubsub
        self.task = task

    async def unsubscribe(self):
        await self.pubsub.unsubscribe(self.subject)
        self.task.cancel()
        with suppress(asyncio.CancelledError):
            await self.task


@async_to_sync_class
class RedisMessageQueue(BaseMessageQueue):
    """
    A wrapper around Redis, which uses two different key patterns:
    - bbot:stream:{subject}: for persistent, tailable queues - e.g. events, activities
    - bbot:work:{subject}: for one-time messages, e.g. tasks

    .publish()/subscribe() are used for persistent queues, which can grow in size up to max_msgs.
    These can be tailed/consumed at any time by multiple consumers.

    .get()/.put() are used for one-off messages, which are deleted after consumption. These act just like a python queue.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._consumers = {}  # Store consumers by subject
        self._active_subscriptions = []
        self._pubsub = None
        self._subscription_tasks = {}

    async def setup(self):
        self.log.debug(f"Setting up Redis message queue at {self.uri}")

        while True:
            try:
                # Parse Redis URI (redis://host:port/db)
                self.redis = redis.from_url(self.uri)
                # Test connection
                await self.redis.ping()
                self._pubsub = self.redis.pubsub()
                break
            except Exception as e:
                self.log.error(f"Failed to connect to Redis at {self.uri}: {e}, retrying...")
                self.log.error(traceback.format_exc())
                await asyncio.sleep(1)

    async def make_taskiq_broker(self):
        return RedisStreamBroker(self.uri)

    async def get(self, subject: str, timeout=None):
        subject = f"bbot:work:{subject}"

        try:
            # Use BLPOP for blocking pop with timeout
            if timeout is not None:
                result = await self.redis.blpop(subject, timeout=timeout)
                if result is None:
                    raise TimeoutError(f"Timed out waiting for message from {subject}")
                _, data = result
            else:
                # Non-blocking pop
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
        """
        Publish a message to the message queue.

        Message can be either raw bytes, a Pydantic model, or a dictionary.
        """
        stream_subject = f"bbot:stream:{subject}"
        pub_subject = f"bbot:pub:{subject}"
        message = smart_encode(message)

        # Store in a list for persistence and history
        await self.redis.rpush(stream_subject, message)
        # Trim the list to maintain max size
        await self.redis.ltrim(stream_subject, -10000, -1)

        # Also publish for real-time subscribers
        await self.redis.publish(pub_subject, message)

    async def subscribe(self, callback, subject: str, durable: str = None):
        """
        Subscribe to a subject. If 'durable' is provided, it will pick up where it left off.
        """
        stream_subject = f"bbot:stream:{subject}"
        pub_subject = f"bbot:pub:{subject}"

        # If durable, we need to track the last processed message
        last_id_key = f"bbot:last_id:{subject}:{durable}" if durable else None

        # First, process any historical messages if durable
        if durable:
            # Get the last processed ID
            last_id = await self.redis.get(last_id_key)
            last_id = int(last_id) if last_id else 0

            # Get all messages since last_id
            messages = await self.redis.lrange(stream_subject, last_id, -1)
            for i, msg_data in enumerate(messages):
                message_json = orjson.loads(msg_data)
                await callback(message_json)
                # Update last processed ID
                if durable:
                    await self.redis.set(last_id_key, last_id + i + 1)

        # Create a dedicated pubsub connection for this subscription
        # to avoid the concurrency issues
        subscriber = self.redis.pubsub()
        await subscriber.subscribe(pub_subject)

        # Create a task to process messages
        async def message_handler():
            try:
                while True:
                    try:
                        message = await subscriber.get_message(ignore_subscribe_messages=True, timeout=1.0)
                        if message and message["type"] == "message":
                            message_json = orjson.loads(message["data"])
                            await callback(message_json)

                            # Update the list length for durable subscriptions
                            if durable:
                                length = await self.redis.llen(stream_subject)
                                await self.redis.set(last_id_key, length)
                    except Exception as e:
                        self.log.error(f"Error processing Redis message: {e}")
                        self.log.error(traceback.format_exc())
                        await asyncio.sleep(1)
            finally:
                # Clean up the subscriber when the task is cancelled
                await subscriber.unsubscribe(pub_subject)
                await subscriber.aclose()

        # Start the message handler task
        task = asyncio.create_task(message_handler())
        self._subscription_tasks[pub_subject] = task

        subscription = Subscription(pub_subject, subscriber, task)
        self._active_subscriptions.append(subscription)
        return subscription

    async def unsubscribe(self, subscription):
        with suppress(Exception):
            await subscription.unsubscribe()
            if subscription in self._active_subscriptions:
                self._active_subscriptions.remove(subscription)

    async def clear(self):
        # Get all keys matching our patterns
        stream_keys = await self.redis.keys("bbot:stream:*")
        work_keys = await self.redis.keys("bbot:work:*")
        last_id_keys = await self.redis.keys("bbot:last_id:*")

        # Delete all keys
        if stream_keys:
            await self.redis.delete(*stream_keys)
        if work_keys:
            await self.redis.delete(*work_keys)
        if last_id_keys:
            await self.redis.delete(*last_id_keys)

    async def cleanup(self):
        # Unsubscribe from all active subscriptions
        for subscription in self._active_subscriptions:
            await self.unsubscribe(subscription)
        self._active_subscriptions = []

        # Cancel all subscription tasks
        for task in self._subscription_tasks.values():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        self._subscription_tasks = {}

        # Close the Redis connection
        if hasattr(self, "redis") and self.redis:
            try:
                await self.redis.aclose()
                self.log.debug("Redis connection closed successfully")
            except Exception as e:
                self.log.error(f"Error closing Redis connection: {e}")
                self.log.error(traceback.format_exc())
