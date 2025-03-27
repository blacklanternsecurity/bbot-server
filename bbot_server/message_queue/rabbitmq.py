import orjson
import asyncio
import aio_pika
import functools
from pydantic import BaseModel
from contextlib import suppress
from taskiq_aio_pika import AioPikaBroker

from .base import BaseMessageQueue
from bbot.models.pydantic import Event


class RabbitMessageQueue(BaseMessageQueue):
    """
    # docker rabbitmq
    docker run --rm -p 5672:5672 -p 5673:5673 rabbitmq:4
    """

    async def setup(self):
        self.connection = None
        self.channel = None

        self._max_queue_length = 1000
        self._queue_kwargs = {
            "durable": False,
            "arguments": {
                "x-max-length": self._max_queue_length,
                "x-overflow": "drop-head",
            },
        }
        self._active_subs = {}

        self.log.debug(f"Setting up message queue at {self.uri}")
        while 1:
            try:
                self.connection = await aio_pika.connect_robust(self.uri)
                self.channel = await self.connection.channel()

                # Declare a single topic exchange for events and assets
                self.exchange = await self.channel.declare_exchange("bbot_exchange", aio_pika.ExchangeType.TOPIC)

                break
            except Exception as e:
                self.log.error(f"Failed to connect to message queue at {self.uri}: {e}, retrying...")
                await asyncio.sleep(1)

    async def make_taskiq_broker(self):
        return AioPikaBroker(url=self.uri)

    async def publish(self, message: BaseModel, subject: str):
        msg_bytes = message.model_dump_json().encode()
        await self.exchange.publish(aio_pika.Message(body=msg_bytes), routing_key=subject)

    async def subscribe(self, callback, subject: str):
        @functools.wraps(callback)
        async def wrapped_callback(message: aio_pika.IncomingMessage):
            message_json = orjson.loads(message.body)
            await callback(message_json)

        queue = await self.channel.declare_queue("", **self._queue_kwargs)  # Use a server-named queue
        await queue.bind(self.exchange, routing_key=subject)  # Bind the queue to the topic exchange with routing key

        consumer_tag = await queue.consume(wrapped_callback)
        self._active_subs[consumer_tag] = queue
        return consumer_tag

    async def unsubscribe(self, consumer_tag):
        await self._active_subs[consumer_tag].cancel(consumer_tag)

    async def cleanup(self):
        # delete all active queues
        for consumer_tag, queue in self._active_subs.items():
            await queue.cancel(consumer_tag)
        queues = set([queue for queue in self._active_subs.values()])
        for queue in queues:
            await queue.delete()
        self._active_subs = {}

        # close the channel and connection
        with suppress(BaseException):
            await self.channel.close()
        self.log.info("Channel closed successfully.")
        with suppress(BaseException):
            await self.connection.close()
        self.log.info("Connection closed successfully.")
