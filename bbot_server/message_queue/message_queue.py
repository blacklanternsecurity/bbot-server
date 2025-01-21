import orjson
import asyncio
import logging
import aio_pika
from contextlib import suppress
from omegaconf import OmegaConf

from bbot_server.config import BBOT_SERVER_CONFIG


class MessageQueue:
    """
    # docker rabbitmq
    docker run --rm -p 5672:5672 -p 5673:5673 rabbitmq:4
    """

    config_key = "message_queue"

    def __init__(self, config=None):
        self.log = logging.getLogger(__name__)
        self.global_config = BBOT_SERVER_CONFIG
        try:
            self.config = self.global_config[self.config_key]
            if config is not None:
                self.config = OmegaConf.merge(self.config, config)
        except Exception as e:
            raise ValueError("Message queue configuration is missing") from e
        try:
            self.uri = self.config.uri
        except Exception as e:
            raise ValueError("Message queue URI is missing") from e
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
        self._active_queues = []

    async def setup(self):
        self.log.info(f"Setting up message queue at {self.uri}")
        while True:
            try:
                self.connection = await aio_pika.connect_robust(self.uri)
                self.channel = await self.connection.channel()

                # Declare a single topic exchange for events and assets
                self.exchange = await self.channel.declare_exchange("bbot_exchange", aio_pika.ExchangeType.TOPIC)

                break
            except Exception as e:
                self.log.error(f"Failed to connect to message queue at {self.uri}: {e}, retrying...")
                await asyncio.sleep(1)

    async def event_subscribe(self, callback):
        queue = await self.channel.declare_queue("", **self._queue_kwargs)  # Use a server-named queue
        await queue.bind(
            self.exchange, routing_key="bbot.events"
        )  # Bind the queue to the topic exchange with routing key

        async def wrapped_callback(message: aio_pika.IncomingMessage):
            async with message.process():
                await callback(message)

        consumer_tag = await queue.consume(wrapped_callback)
        self._active_queues.append((queue, consumer_tag))

    async def event_publish(self, message):
        msg_bytes = orjson.dumps(message)
        await self.exchange.publish(aio_pika.Message(body=msg_bytes), routing_key="bbot.events")

    async def event_tail(self):
        """
        Tail new events as they come in

        To accomplish this, we create our own dedicated python queue and a rabbitmq callback to feed it.
        """
        q = asyncio.Queue()

        async def callback(msg):
            await q.put(msg)

        await self.event_subscribe(callback)

        while 1:
            try:
                message = await asyncio.wait_for(q.get(), timeout=0.1)
                yield orjson.loads(message.body)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    async def asset_subscribe(self, callback):
        async def wrapped_callback(message: aio_pika.IncomingMessage):
            async with message.process():
                await callback(message)

        queue = await self.channel.declare_queue("", **self._queue_kwargs)  # Use a server-named queue
        await queue.bind(
            self.exchange, routing_key="bbot.assets"
        )  # Bind the queue to the topic exchange with routing key

        consumer_tag = await queue.consume(wrapped_callback)
        self._active_queues.append((queue, consumer_tag))

    async def asset_publish(self, message):
        msg_bytes = orjson.dumps(message)
        await self.exchange.publish(aio_pika.Message(body=msg_bytes), routing_key="bbot.assets")

    async def asset_tail(self, lines=10):
        q = asyncio.Queue()

        async def callback(msg: aio_pika.IncomingMessage):
            async with msg.process():
                await q.put(msg)

        # Declare a server-named queue and bind it to the exchange with the correct routing key
        queue = await self.channel.declare_queue("", **self._queue_kwargs)
        await queue.bind(self.exchange, routing_key="bbot.assets")

        consumer_tag = await queue.consume(callback)
        self._active_queues.append((queue, consumer_tag))

        # first, read everything from the queue
        tail_lines = []
        while 1:
            try:
                message = await asyncio.wait_for(q.get(), timeout=0.1)
                tail_lines.append(orjson.loads(message.body))
            except (asyncio.QueueEmpty, asyncio.TimeoutError):
                break
        tail_lines = tail_lines[-lines:]
        for line in tail_lines:
            yield line

        # then, consume new messages
        while 1:
            message = await q.get()
            yield orjson.loads(message.body)

    async def cleanup(self):
        # delete all active queues
        for queue, consumer_tag in self._active_queues:
            await queue.cancel(consumer_tag)
        queues = set([queue for queue, _ in self._active_queues])
        for queue in queues:
            await queue.delete()
        self._active_queues = []

        # close the channel and connection
        # if self.channel and not self.channel.is_closed:
        await self.channel.close()
        self.log.info("Channel closed successfully.")
        # if self.connection and not self.connection.is_closed:
        await self.connection.close()
        self.log.info("Connection closed successfully.")

        all_tasks = asyncio.all_tasks()

        for task in all_tasks:
            # Get the coroutine object
            coro = task.get_coro()

            # Get the qualified name (includes module path)
            qualified_name = coro.cr_code.co_qualname
            if "Channel._" in qualified_name or "Connection._" in qualified_name:
                task.cancel()
                with suppress(BaseException):
                    await task
