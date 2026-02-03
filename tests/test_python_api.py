import pytest
import asyncio
import logging
from time import sleep
from contextlib import suppress

from bbot_server import BBOTServer
from bbot_server.errors import BBOTServerNotFoundError
from bbot_server.utils.async_utils import AsyncToSyncWrapper, async_to_sync_class

log = logging.getLogger(__name__)


async def test_async_to_sync_wrappers():
    ### basic sync/async function calls ###

    wrapper = AsyncToSyncWrapper()
    wrapper.start()

    async def my_coroutine():
        await asyncio.sleep(0.11)
        return "Hello, World!"

    result = wrapper.run_coroutine(my_coroutine())
    assert result == "Hello, World!"

    ### class decorator ###

    @async_to_sync_class
    class MyAsyncClass:
        async def async_method(self):
            await asyncio.sleep(0.1)
            return "Hello, World!"

    sync_obj = MyAsyncClass(synchronous=True)
    result = sync_obj.async_method()
    assert result == "Hello, World!"

    async_obj = MyAsyncClass(synchronous=False)
    result = await async_obj.async_method()
    assert result == "Hello, World!"


async def test_async_generators():
    @async_to_sync_class
    class AsyncGeneratorClass:
        async def async_generator(self, count=5, delay=0.05):
            """A simple async generator that yields integers with delays."""
            for i in range(count):
                await asyncio.sleep(delay)
                yield i

        async def async_method(self):
            """Regular async method for comparison."""
            await asyncio.sleep(0.1)
            return "Regular method"

    # Test synchronous usage
    sync_obj = AsyncGeneratorClass(synchronous=True)

    # Test regular method still works
    assert sync_obj.async_method() == "Regular method"

    # Test synchronous iteration over async generator
    collected_items = []
    for item in sync_obj.async_generator(count=3, delay=0.01):
        collected_items.append(item)

    assert collected_items == [0, 1, 2]

    # Test asynchronous usage
    async_obj = AsyncGeneratorClass(synchronous=False)

    # Test async iteration
    async_collected_items = []
    async for item in async_obj.async_generator(count=3, delay=0.01):
        async_collected_items.append(item)

    assert async_collected_items == [0, 1, 2]

    # Test that generator is properly closed
    # This is harder to test directly, but we can verify it doesn't raise exceptions
    gen = sync_obj.async_generator(count=2, delay=0.01)
    assert next(gen) == 0
    assert next(gen) == 1

    # This should exhaust the generator and trigger the finally block with aclose()
    with pytest.raises(StopIteration):
        next(gen)


def _test_synchronous_api(interface, bbot_events):
    log.info(f"Testing synchronous API with interface: {interface}")
    bbot_server = BBOTServer(interface=interface, synchronous=True)
    try:
        assert bbot_server._setup_finished == False
        setup_result = bbot_server.setup()
        assert setup_result == (True, "")
        assert bbot_server._setup_finished == True

        bbot_event = bbot_events[0][0]

        # event store should be empty
        assert list(bbot_server.list_events()) == []
        with pytest.raises(BBOTServerNotFoundError, match=f"Event {bbot_event.uuid} not found"):
            bbot_server.get_event(bbot_event.uuid)

        # insert one event
        bbot_server.insert_event(bbot_event)
        sleep(0.5)

        # we should now have one event
        events = list(bbot_server.list_events())
        assert events == [bbot_event]

        events = list(bbot_server.query_events())
        assert len(events) == 1

        event = bbot_server.get_event(bbot_event.uuid)
        assert event == bbot_event
    finally:
        with suppress(Exception):
            bbot_server.cleanup()


def test_synchronous_api_python(bbot_server_http, bbot_events, mongo_cleanup, bbot_watchdog):
    _test_synchronous_api("python", bbot_events)


def test_synchronous_api_http(bbot_server_http, bbot_events, mongo_cleanup, bbot_watchdog):
    _test_synchronous_api("http", bbot_events)
