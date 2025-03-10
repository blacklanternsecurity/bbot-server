import asyncio
import logging

from bbot_server import BBOTServer

log = logging.getLogger(__name__)

async def test_async_to_sync_wrappers():
    from bbot_server.utils.async_utils import AsyncToSyncWrapper, async_to_sync_class

    ### basic sync/async function calls ###

    wrapper = AsyncToSyncWrapper()
    wrapper.start()

    async def my_coroutine():
        await asyncio.sleep(.11)
        return "Hello, World!"

    result = wrapper.run_coroutine(my_coroutine())
    assert result == "Hello, World!"

    wrapper.stop()

    ### class decorator ###

    @async_to_sync_class
    class MyAsyncClass:
        async def async_method(self):
            await asyncio.sleep(.1)
            return "Hello, World!"

    sync_obj = MyAsyncClass(synchronous=True)
    result = sync_obj.async_method()
    assert result == "Hello, World!"

    async_obj = MyAsyncClass(synchronous=False)
    result = await async_obj.async_method()
    assert result == "Hello, World!"



def _test_sychronous_api(interface):
    log.info(f"Testing synchronous API with interface: {interface}")
    bbot_server = BBOTServer(interface=interface, synchronous=True)
    bbot_server.setup()

    scans = bbot_server.get_scans()
    assert scans == []



def test_sychronous_api_python(bbot_server_http):
    _test_sychronous_api("python")



async def test_sychronous_api_http(bbot_server_http):
    await bbot_server_http()
    _test_sychronous_api("http")

