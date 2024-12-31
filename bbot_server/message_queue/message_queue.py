import orjson
import asyncio
from omegaconf import OmegaConf
from nats.aio.client import Client as NATS

from bbot_server.config import BBOT_SERVER_CONFIG


class MessageQueue:
    config_key = "message_queue"

    def __init__(self, config=None):
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
        self.nc = NATS()

    async def setup(self):
        await self.nc.connect(self.uri)

    async def event_subscribe(self, callback):
        return await self.nc.subscribe("events", cb=callback)

    async def event_publish(self, message):
        msg_bytes = orjson.dumps(message)
        return await self.nc.publish("events", msg_bytes)

    async def asset_subscribe(self, callback):
        return await self.nc.subscribe("assets", cb=callback)

    async def asset_publish(self, message):
        msg_bytes = orjson.dumps(message)
        return await self.nc.publish("assets", msg_bytes)

    async def asset_tail(self):
        q = asyncio.Queue()

        async def callback(msg):
            q.put_nowait(msg)

        await self.nc.subscribe("assets", cb=callback)
        while True:
            message = await q.get()
            yield orjson.loads(message.data)

    async def cleanup(self):
        await self.nc.close()
