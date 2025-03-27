import pytest
import asyncio
from contextlib import suppress

from tests.test_applets.base import BaseAppletTest


@pytest.mark.asyncio
async def test_fifo_queue_nats(bbot_server):
    bbot_server = await bbot_server()

    # first, we test the basic put/get functionality
    await bbot_server.message_queue.put({"test1": "test1"}, "test")
    await bbot_server.message_queue.put({"test2": "test2"}, "test")
    message1 = await bbot_server.message_queue.get("test", timeout=0.1)
    assert message1 == {"test1": "test1"}
    message2 = await bbot_server.message_queue.get("test", timeout=0.1)
    assert message2 == {"test2": "test2"}
    with pytest.raises(TimeoutError):
        await bbot_server.message_queue.get("test", timeout=0.1)


class TestMessageQueuesNATS(BaseAppletTest):
    config_overrides = {
        "message_queue": {
            "uri": "nats://localhost:4222",
        }
    }
    needs_watchdog = True

    expected_message_queue_uri = "nats://localhost:4222"

    async def setup(self):
        assert self.bbot_server.message_queue.uri == self.expected_message_queue_uri

        await self.bbot_server.message_queue.clear()

        self.message_queue_assets = []
        self.message_queue_events = []
        self.message_queue_event_task, self.message_queue_asset_task = await self.setup_activities(
            self.message_queue_events, self.message_queue_assets
        )

        # test some basic pub/sub functionality (makes sure messages are queued persistently)
        event = self.scan1_events[0]
        await self.bbot_server.message_queue.publish(event, "events")
        # wait a second
        await asyncio.sleep(0.1)
        # read the message back
        events = []

        async def callback(message):
            events.append(message)

        sub = await self.bbot_server.message_queue.subscribe(callback, "events")
        await asyncio.sleep(0.1)
        assert len(events) == 1
        assert events[0] == event.model_dump()
        await self.bbot_server.message_queue.unsubscribe(sub)

        # okay, now we test durable consumers (makes sure a consumer won't be fed the same event twice)
        # the server should remember where it left off
        events.clear()
        sub = await self.bbot_server.message_queue.subscribe(callback, "events", durable="test_durable")
        await asyncio.sleep(0.1)
        assert len(events) == 1
        await self.bbot_server.message_queue.unsubscribe(sub)
        # this sleep is critical, otherwise you'll run into the race condition: "JetStream.Error consumer is already bound to a subscription"
        await asyncio.sleep(0.1)

        events.clear()
        sub = await self.bbot_server.message_queue.subscribe(callback, "events", durable="test_durable")
        await asyncio.sleep(0.1)
        assert len(events) == 0
        await self.bbot_server.message_queue.unsubscribe(sub)
        await asyncio.sleep(0.1)

        events.clear()
        sub = await self.bbot_server.message_queue.subscribe(callback, "events", durable="test_durable_new")
        await asyncio.sleep(0.1)
        assert len(events) == 1
        await self.bbot_server.message_queue.unsubscribe(sub)

        await self.bbot_server.message_queue.clear()

    async def after_scan_1(self):
        # here, we verify that both our queue tasks received the exact same messages
        assert self.asset_messages
        assert self.message_queue_assets
        assert len(self.message_queue_assets) == len(self.asset_messages)
        assert sorted(self.message_queue_assets, key=lambda x: x.timestamp) == sorted(
            self.asset_messages, key=lambda x: x.timestamp
        )

        assert self.event_messages
        assert self.message_queue_events
        assert len(self.message_queue_events) == len(self.event_messages)
        assert sorted(self.message_queue_events, key=lambda x: x.timestamp) == sorted(
            self.event_messages, key=lambda x: x.timestamp
        )

        self.asset_messages_len = len(self.asset_messages)
        self.event_messages_len = len(self.event_messages)

    async def after_scan_2(self):
        # make sure we received more messages
        assert len(self.asset_messages) > self.asset_messages_len
        assert len(self.event_messages) > self.event_messages_len
        # and that our two tasks still received the same ones
        await self.after_scan_1()

    async def cleanup(self):
        with suppress(BaseException):
            for task in [self.message_queue_asset_task, self.message_queue_event_task]:
                task.cancel()
                with suppress(BaseException):
                    await task


# class TestMessageQueuesRabbitMQ(TestMessageQueuesNATS):
#     config_overrides = {
#         "message_queue": {
#             "uri": "amqp://localhost:5672",
#         }
#     }

#     expected_message_queue_uri = "amqp://localhost:5672"
