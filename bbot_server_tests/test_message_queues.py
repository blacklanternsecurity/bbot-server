from contextlib import suppress

from bbot_server_tests.test_applets.base import BaseAppletTest


class TestMessageQueuesNATS(BaseAppletTest):
    config_overrides = {
        "message_queue": {
            "uri": "nats://localhost:4222",
        }
    }

    expected_message_queue_uri = "nats://localhost:4222"

    async def setup(self):
        self.message_queue_assets = []
        self.message_queue_events = []
        self.message_queue_event_task, self.message_queue_asset_task = self.setup_activities(
            self.message_queue_events, self.message_queue_assets
        )
        assert self.bbot_server.message_queue.uri == self.expected_message_queue_uri

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


class TestMessageQueuesRabbitMQ(TestMessageQueuesNATS):
    config_overrides = {
        "message_queue": {
            "uri": "amqp://localhost:5672",
        }
    }

    expected_message_queue_uri = "amqp://localhost:5672"
