import orjson
import asyncio
import logging
import aio_pika
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

        self._max_queue_length = 100000
        self._queue_kwargs = {
            "durable": False,
            "arguments": {
                "x-max-length": self._max_queue_length,
                "x-overflow": "drop-head",
                "x-stream-offset": "last",
                "x-stream-filter-size": 10,
            },
        }

    async def setup(self):
        self.log.info(f"Setting up message queue at {self.uri}")
        while True:
            try:
                self.connection = await aio_pika.connect_robust(self.uri)
                self.channel = await self.connection.channel()
                break
            except Exception as e:
                self.log.error(f"Failed to connect to message queue at {self.uri}: {e}, retrying...")
                await asyncio.sleep(1)

    async def event_subscribe(self, callback):
        queue = await self.channel.declare_queue("events", **self._queue_kwargs)
        await queue.consume(callback)

    async def event_publish(self, message):
        msg_bytes = orjson.dumps(message)
        await self.channel.default_exchange.publish(aio_pika.Message(body=msg_bytes), routing_key="events")

    async def asset_subscribe(self, callback):
        queue = await self.channel.declare_queue("assets", **self._queue_kwargs)
        await queue.consume(callback)

    async def asset_publish(self, message):
        msg_bytes = orjson.dumps(message)
        await self.channel.default_exchange.publish(aio_pika.Message(body=msg_bytes), routing_key="assets")

    async def asset_tail(self, lines=10):
        q = asyncio.Queue()

        async def callback(msg):
            await q.put(msg)

        queue = await self.channel.declare_queue(
            "assets",
            durable=False,
            arguments={'x-max-length': self._max_queue_length, "x-overflow": "drop-head"}
        )
        await self.channel.set_qos(prefetch_count=lines)
        await queue.consume(callback)
        while True:
            message = await q.get()
            yield orjson.loads(message.body)

    async def cleanup(self):
        await self.connection.close()
