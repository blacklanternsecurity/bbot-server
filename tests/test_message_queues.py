import pytest
import asyncio
from contextlib import suppress

from tests.test_applets.base import BaseAppletTest


async def _test_fifo_queue(bbot_server):
    # first, we test the basic put/get functionality
    await bbot_server.message_queue.put({"test1": "test1"}, "test")
    await bbot_server.message_queue.put({"test2": "test2"}, "test")
    message1 = await bbot_server.message_queue.get("test", timeout=0.1)
    assert message1 == {"test1": "test1"}
    message2 = await bbot_server.message_queue.get("test", timeout=0.1)
    assert message2 == {"test2": "test2"}
    with pytest.raises(TimeoutError):
        await bbot_server.message_queue.get("test", timeout=0.1)


async def _test_basic_subscribe(bbot_server):
    ### BASIC NON-DURABLE SUBSCRIPTION TEST ###

    messages1 = []
    messages2 = []

    async def callback1(message):
        messages1.append(message)

    # Subscribe to a test channel
    sub1 = await bbot_server.message_queue.subscribe(callback1, "test_channel")

    await asyncio.sleep(0.2)

    # Publish first message
    message1 = {"id": 1, "content": "test message 1"}
    await bbot_server.message_queue.publish(message1, "test_channel")
    await asyncio.sleep(0.2)

    # Verify first message was received
    assert messages1 == [message1]

    # Subscribe to the channel again
    async def callback2(message):
        messages2.append(message)

    sub2 = await bbot_server.message_queue.subscribe(callback2, "test_channel")
    await asyncio.sleep(0.2)

    assert messages2 == []

    # Publish second message
    message2 = {"id": 2, "content": "test message 2"}
    await bbot_server.message_queue.publish(message2, "test_channel")
    await asyncio.sleep(0.2)

    assert messages1 == [message1, message2]
    assert messages2 == [message2]

    await sub1.unsubscribe()
    await sub2.unsubscribe()


async def _test_durable_subscribe(bbot_server):
    ### DURABLE SUBSCRIPTION TEST ###

    messages1 = []
    messages2 = []

    async def callback1(message):
        messages1.append(message)

    async def callback2(message):
        messages2.append(message)

    # Publish initial messages before any subscriptions
    message1 = {"id": 1, "content": "durable test message 1"}
    message2 = {"id": 2, "content": "durable test message 2"}
    await bbot_server.message_queue.publish(message1, "durable_channel")
    await bbot_server.message_queue.publish(message2, "durable_channel")
    await asyncio.sleep(0.2)

    # Create first durable subscription - should receive all historical messages
    sub1 = await bbot_server.message_queue.subscribe(callback1, "durable_channel", durable="test_consumer1")
    await asyncio.sleep(0.2)

    # Verify first subscription received both historical messages
    assert messages1 == [message1, message2]

    # Publish a new message
    message3 = {"id": 3, "content": "durable test message 3"}
    await bbot_server.message_queue.publish(message3, "durable_channel")
    await asyncio.sleep(0.2)

    # Verify first subscription received the new message
    assert messages1 == [message1, message2, message3]

    # Unsubscribe and resubscribe with the same durable name
    await sub1.unsubscribe()
    await asyncio.sleep(0.2)

    # Clear the messages list to verify what new messages are received
    messages1.clear()

    # Resubscribe with the same durable name - should NOT receive previous messages
    sub1 = await bbot_server.message_queue.subscribe(callback1, "durable_channel", durable="test_consumer1")
    await asyncio.sleep(0.2)

    # Verify no messages were received (since we've already processed them)
    assert messages1 == []

    # Create a second durable subscription with a different name - should receive all messages
    sub2 = await bbot_server.message_queue.subscribe(callback2, "durable_channel", durable="test_consumer2")
    await asyncio.sleep(0.2)

    # Verify second subscription received all historical messages
    assert messages2 == [message1, message2, message3]

    # Publish a new message that both subscriptions should receive
    message4 = {"id": 4, "content": "durable test message 4"}
    await bbot_server.message_queue.publish(message4, "durable_channel")
    await asyncio.sleep(0.2)

    # Verify both subscriptions received the new message
    assert messages1 == [message4]
    assert messages2 == [message1, message2, message3, message4]

    # Clean up
    await sub1.unsubscribe()
    await sub2.unsubscribe()
    await asyncio.sleep(0.2)


@pytest.mark.asyncio
async def test_queues_redis(bbot_server):
    # Override the message queue URI for this test
    bbot_server = await bbot_server(config_overrides={"message_queue": {"uri": "redis://localhost:6379"}})
    await bbot_server.message_queue.clear()
    await _test_fifo_queue(bbot_server)
    await _test_basic_subscribe(bbot_server)
    await _test_durable_subscribe(bbot_server)
    await bbot_server.message_queue.clear()


class TestMessageQueuesRedis(BaseAppletTest):
    config_overrides = {
        "message_queue": {
            "uri": "redis://localhost:6379",
        }
    }
    needs_watchdog = True

    expected_message_queue_uri = "redis://localhost:6379"

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
        await asyncio.sleep(0.2)

        # read the message back
        events = []

        async def callback(message):
            events.append(message)

        # not durable, so historical message won't show up
        sub = await self.bbot_server.message_queue.subscribe(callback, "events")
        await asyncio.sleep(0.2)
        assert events == []
        await self.bbot_server.message_queue.unsubscribe(sub)

        # there should be one historical message
        events.clear()
        sub = await self.bbot_server.message_queue.subscribe(callback, "events", durable="test_durable")
        await asyncio.sleep(0.2)
        assert len(events) == 1
        await self.bbot_server.message_queue.unsubscribe(sub)

        events.clear()
        sub = await self.bbot_server.message_queue.subscribe(callback, "events", durable="test_durable")
        await asyncio.sleep(0.2)
        # there should be no new events
        assert len(events) == 0
        event2 = self.scan1_events[1]
        await self.bbot_server.message_queue.publish(event2, "events")
        await asyncio.sleep(0.2)

        # until we publish a new one
        assert len(events) == 1
        await self.bbot_server.message_queue.unsubscribe(sub)
        await asyncio.sleep(0.2)

        events.clear()
        sub = await self.bbot_server.message_queue.subscribe(callback, "events", durable="test_durable_new")
        await asyncio.sleep(0.2)
        assert len(events) == 2
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


# class TestMessageQueuesRedis(TestMessageQueuesNATS):
#     config_overrides = {"message_queue": {"uri": "redis://localhost:6379"}}
#     needs_watchdog = True

#     expected_message_queue_uri = "redis://localhost:6379"
