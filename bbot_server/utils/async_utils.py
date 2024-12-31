import asyncio
import inspect
import threading
from cachetools import LRUCache
from contextlib import asynccontextmanager


class _Lock(asyncio.Lock):
    def __init__(self, name):
        self.name = name
        super().__init__()


class NamedLock:
    """
    Returns a unique asyncio.Lock() based on a provided string

    Useful for preventing multiple operations from occurring on the same data in parallel
    E.g. simultaneous DB lookups on the same asset
    """

    def __init__(self, max_size=1000):
        self._cache = LRUCache(maxsize=max_size)

    @asynccontextmanager
    async def lock(self, name):
        try:
            lock = self._cache[name]
        except KeyError:
            lock = _Lock(name)
            self._cache[name] = lock
        async with lock:
            yield


class AsyncToSyncWrapper:
    """Manages a background event loop for running async code synchronously.

    This class creates and manages a separate thread with an event loop,
    allowing asynchronous coroutines to be run synchronously from the main thread.

    Attributes:
        loop (asyncio.AbstractEventLoop): The event loop running in the background thread.
        thread (threading.Thread): The background thread running the event loop.

    Example:
        wrapper = AsyncToSyncWrapper()
        wrapper.start()

        async def my_coroutine():
            await asyncio.sleep(1)
            return "Hello, World!"

        result = wrapper.run_coroutine(my_coroutine())
        print(result)  # Prints: Hello, World!

        wrapper.stop()
    """

    def __init__(self):
        self.loop = None
        self.thread = None
        self._ready = threading.Event()

    def start(self):
        """Starts the background thread and event loop.

        This method must be called before run_coroutine().
        """

        def run_event_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self._ready.set()  # Signal that the loop is ready
            self.loop.run_forever()

        self.thread = threading.Thread(target=run_event_loop, daemon=True)
        self.thread.start()
        self._ready.wait()  # Wait for the loop to be ready

    def stop(self):
        """Stops the background event loop and joins the thread.

        This method should be called to clean up resources when done.
        """
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.thread:
            self.thread.join()

    def run_coroutine(self, coro):
        """Runs a coroutine in the background event loop and returns the result.

        Args:
            coro (coroutine): The coroutine to run.

        Returns:
            The result of the coroutine.

        Raises:
            RuntimeError: If the event loop is not running (start() wasn't called).
        """
        if not self.loop:
            raise RuntimeError("Event loop is not running. Call start() first.")
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result()


def async_to_sync_class(cls):
    """Decorator that allows async class methods to be called synchronously.

    This decorator wraps a class, adding a 'synchronous' parameter to its
    constructor. When True, async methods are executed synchronously using
    the current event loop, without blocking it.

    Args:
        cls: The class to be decorated.

    Returns:
        A new class that wraps the original, with the ability to call async
        methods synchronously.

    Example:
        @async_to_sync_class
        class MyAsyncClass:
            async def async_method(self):
                await asyncio.sleep(1)
                return "Hello, World!"

        # Synchronous usage
        sync_obj = MyAsyncClass(synchronous=True)
        result = sync_obj.async_method()  # Runs synchronously

        # Asynchronous usage
        async_obj = MyAsyncClass(synchronous=False)
        async def run_async():
            result = await async_obj.async_method()
    """

    class Wrapper(cls):
        def __init__(self, *args, synchronous=False, **kwargs):
            self._synchronous = synchronous
            super().__init__(*args, **kwargs)
            if self._synchronous:
                self._wrapper = AsyncToSyncWrapper()
                self._wrapper.start()

        def _wrap(self, attr):
            if callable(attr) and inspect.iscoroutinefunction(attr) and self._synchronous:

                def wrapper(*args, **kwargs):
                    return self._wrapper.run_coroutine(attr(*args, **kwargs))

                return wrapper
            return attr

        def __getattr__(self, name):
            attr = super().__getattr__(name)
            wrap = self.__getattribute__("_wrap")
            return wrap(attr)

        def __del__(self):
            if self.__getattribute__("_synchronous"):
                self._wrapper.stop()

    return Wrapper
