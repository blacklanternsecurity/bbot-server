import atexit
import asyncio
import inspect
import logging
import threading
from functools import wraps
from cachetools import LRUCache
from contextlib import asynccontextmanager

log = logging.getLogger("bbot.server.utils.async_utils")


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
            try:
                self.loop.run_forever()
            finally:
                self.loop.stop()
                self.loop.close()

        self.thread = threading.Thread(target=run_event_loop, daemon=True)
        self.thread.start()
        self._ready.wait()  # Wait for the loop to be ready

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
    """Decorator that allows async class methods to be called synchronously."""

    # Store the original __new__ method
    orig_new = cls.__new__

    # Define a new __new__ method that handles the synchronous parameter
    def __new__(mcs, *args, synchronous=False, **kwargs):
        # Create the instance using the original __new__
        instance = orig_new(cls)  # Only create the instance, don't pass args yet

        # If synchronous mode is requested, wrap the instance
        if synchronous:
            wrapper = _SyncWrapper(instance)
            # Initialize the original instance
            instance.__init__(*args, **kwargs)
            return wrapper

        return instance

    # Replace the __new__ method
    cls.__new__ = __new__

    # Define the wrapper class in the closure
    class _SyncWrapper:
        def __init__(self, instance):
            self._instance = instance
            self._wrapper = AsyncToSyncWrapper()
            self._wrapper.start()

        def _async_wrap(self, attr):
            """
            Gracefully wraps async functions and generators so they can be called synchronously
            """
            # Skip wrapping if not synchronous or not callable
            if not callable(attr):
                return attr

            # Handle regular async functions
            if inspect.iscoroutinefunction(attr):

                def wrapper(*args, **kwargs):
                    return self._wrapper.run_coroutine(attr(*args, **kwargs))

                return wrapper

            # Handle async generator functions
            elif inspect.isasyncgenfunction(attr):

                def wrapper(*args, **kwargs):
                    # Get the async generator object
                    async_gen = attr(*args, **kwargs)

                    # Create a synchronous generator that yields from the async generator
                    def sync_generator():
                        try:
                            while True:
                                # Get the next item from the async generator
                                coro = async_gen.__anext__()
                                try:
                                    # Run the coroutine synchronously and yield its result
                                    yield self._wrapper.run_coroutine(coro)
                                except StopAsyncIteration:
                                    # This is raised when the async generator is exhausted
                                    break
                        finally:
                            # Ensure the async generator is properly closed
                            if hasattr(async_gen, "aclose"):
                                self._wrapper.run_coroutine(async_gen.aclose())

                    # Return the synchronous generator
                    return sync_generator()

                return wrapper

            return attr

        def __getattr__(self, name):
            attr = getattr(self._instance, name)
            return self._async_wrap(attr)

    return cls


async def tail_queue(q):
    while 1:
        try:
            yield await asyncio.wait_for(q.get(), timeout=0.1)
        except asyncio.QueueEmpty:
            await asyncio.sleep(0.1)
        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            break
