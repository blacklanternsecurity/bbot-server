import atexit
import asyncio
import inspect
import logging
import threading
from cachetools import LRUCache
from functools import wraps, partial
from contextlib import asynccontextmanager

log = logging.getLogger("bbot_server.utils.async_utils")


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
    """

    def __init__(self):
        self.log = logging.getLogger("bbot_server.utils.async_utils")
        self.loop = None
        self.thread = None

    def start(self):
        """Starts the background thread and event loop.

        This method must be called before run_coroutine().
        """
        self._ready = threading.Event()

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
        atexit.register(self.shutdown)

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

    def shutdown(self):
        """
        Properly shut down the background thread and event loop.

        Note: using this atexit is problematic because it executes prematurely when CTRL+C is pressed
        """
        pass
        # loop = getattr(self, "loop", None)
        # if loop is not None and loop.is_running():
        #     self.loop.call_soon_threadsafe(self.loop.stop)
        #     thread = getattr(self, "thread", None)
        #     if thread is not None:
        #         thread.join(timeout=5)  # Wait for thread to finish


def async_to_sync_class(cls):
    """
    Decorator that allows async class methods to be called synchronously.

    When a class is instantiated with synchronous=True, it returns a wrapper
    that makes all async methods callable synchronously.
    """
    # Store the original __new__
    original_new = cls.__new__

    @staticmethod
    def new_new(cls, *args, **kwargs):
        # Extract synchronous parameter if present
        synchronous = kwargs.pop("synchronous", False)

        # Create the instance using the original __new__ and initialize it
        if original_new is object.__new__:
            instance = original_new(cls)
            instance.__init__(*args, **kwargs)
        else:
            # If __new__ is overridden, let it handle initialization
            instance = original_new(cls, *args, **kwargs)

        # If synchronous mode is requested, wrap the instance
        if synchronous:
            return _SyncWrapper(instance)

        return instance

    # Replace __new__
    cls.__new__ = new_new

    # Define the wrapper class
    class _SyncWrapper:
        def __init__(self, instance):
            self._instance = instance
            self._wrapper = AsyncToSyncWrapper()
            self._wrapper.start()

        def _async_wrap(self, attr):
            """
            Gracefully wraps async functions and generators so they can be called synchronously
            """
            # Skip wrapping if not callable
            if not callable(attr):
                return attr

            # Handle regular async functions
            if inspect.iscoroutinefunction(attr) or (
                isinstance(attr, partial) and inspect.iscoroutinefunction(attr.func)
            ):

                @wraps(attr)
                def wrapper(*args, **kwargs):
                    return self._wrapper.run_coroutine(attr(*args, **kwargs))

                return wrapper

            # Handle async generators
            elif inspect.isasyncgenfunction(attr) or (
                isinstance(attr, partial) and inspect.isasyncgenfunction(attr.func)
            ):

                @wraps(attr)
                def wrapper(*args, **kwargs):
                    # Get the async generator object
                    async_gen = attr(*args, **kwargs)

                    # Create a synchronous generator that yields from the async generator
                    def sync_generator():
                        # try:
                        while True:
                            # Get the next item from the async generator
                            coro = async_gen.__anext__()
                            try:
                                # Run the coroutine synchronously and yield its result
                                yield self._wrapper.run_coroutine(coro)
                            except StopAsyncIteration:
                                # This is raised when the async generator is exhausted
                                break
                        # finally:
                        #     with suppress(RuntimeError):
                        #         # Ensure the async generator is properly closed
                        #         if hasattr(async_gen, "aclose"):
                        #             self._wrapper.run_coroutine(async_gen.aclose())

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
