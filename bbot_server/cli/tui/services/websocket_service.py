"""
WebSocket service for BBOT Server TUI

Manages WebSocket connections for real-time activity streaming with
auto-reconnection and callback support.
"""
import asyncio
import logging
from typing import Callable, List, Optional, AsyncGenerator

from bbot_server.errors import BBOTServerError


log = logging.getLogger(__name__)


class WebSocketService:
    """
    Service for managing WebSocket connections and streaming data

    Provides real-time activity streaming with automatic reconnection,
    callback support, and exponential backoff on connection failures.
    """

    def __init__(self, bbot_server):
        """
        Initialize the WebSocket service

        Args:
            bbot_server: BBOTServer HTTP client instance
        """
        self.bbot_server = bbot_server
        self._activity_callbacks: List[Callable] = []
        self._is_streaming = False
        self._stream_task: Optional[asyncio.Task] = None

    def subscribe_activities(self, callback: Callable) -> None:
        """
        Subscribe to activity updates

        Args:
            callback: Async function to call with each activity
        """
        if callback not in self._activity_callbacks:
            self._activity_callbacks.append(callback)
            log.debug(f"Subscribed callback: {callback.__name__}")

    def unsubscribe_activities(self, callback: Callable) -> None:
        """
        Unsubscribe from activity updates

        Args:
            callback: Previously subscribed callback function
        """
        if callback in self._activity_callbacks:
            self._activity_callbacks.remove(callback)
            log.debug(f"Unsubscribed callback: {callback.__name__}")

    async def start_activity_stream(self, n: int = 100) -> None:
        """
        Start streaming activities in the background

        Args:
            n: Number of historic activities to fetch initially
        """
        if self._is_streaming:
            log.warning("Activity stream already running")
            return

        self._is_streaming = True
        self._stream_task = asyncio.create_task(self._stream_activities_with_reconnect(n))
        log.info("Started activity stream")

    async def stop_activity_stream(self) -> None:
        """Stop the activity stream"""
        self._is_streaming = False
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass
        log.info("Stopped activity stream")

    async def _stream_activities_with_reconnect(self, n: int = 100) -> None:
        """
        Stream activities with automatic reconnection

        Args:
            n: Number of historic activities to fetch initially
        """
        backoff = 1  # Start with 1 second
        max_backoff = 60  # Maximum 60 seconds

        while self._is_streaming:
            try:
                log.debug("Connecting to activity stream")
                async for activity in self.tail_activities(n=n):
                    if not self._is_streaming:
                        break

                    # Notify all callbacks
                    for callback in self._activity_callbacks:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(activity)
                            else:
                                callback(activity)
                        except Exception as e:
                            log.error(f"Error in activity callback {callback.__name__}: {e}")

                    # Reset backoff on successful message
                    backoff = 1

            except asyncio.CancelledError:
                log.debug("Activity stream cancelled")
                break
            except BBOTServerError as e:
                if not self._is_streaming:
                    break
                log.warning(f"Activity stream error: {e}. Reconnecting in {backoff}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
            except Exception as e:
                if not self._is_streaming:
                    break
                log.error(f"Unexpected error in activity stream: {e}. Reconnecting in {backoff}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

    async def tail_activities(self, n: int = 10) -> AsyncGenerator:
        """
        Tail activities via WebSocket

        Args:
            n: Number of historic activities to fetch

        Yields:
            Activity models as they arrive
        """
        try:
            # The bbot_server client is wrapped with @async_to_sync_class
            # so tail_activities returns a sync generator, not async
            # We need to run it in an executor to make it async
            import asyncio
            loop = asyncio.get_event_loop()

            # Get the sync generator
            sync_gen = self.bbot_server.tail_activities(n=n)

            # Iterate through it in executor to avoid blocking
            while True:
                try:
                    # Run the next() call in a thread to avoid blocking
                    activity = await loop.run_in_executor(None, lambda: next(sync_gen))
                    yield activity
                except StopIteration:
                    break

        except BBOTServerError as e:
            log.error(f"Error tailing activities: {e}")
            raise

    async def list_recent_activities(self, n: int = 50, host: Optional[str] = None,
                                    activity_type: Optional[str] = None) -> List:
        """
        Fetch recent activities without streaming

        Args:
            n: Number of activities to fetch
            host: Filter by host
            activity_type: Filter by activity type

        Returns:
            List of Activity models
        """
        try:
            kwargs = {}
            if host:
                kwargs['host'] = host
            if activity_type:
                kwargs['type'] = activity_type

            activities = list(self.bbot_server.list_activities(**kwargs))
            log.debug(f"Fetched {len(activities)} activities")
            return activities[:n]
        except BBOTServerError as e:
            log.error(f"Error fetching activities: {e}")
            return []

    @property
    def is_streaming(self) -> bool:
        """Check if the service is currently streaming"""
        return self._is_streaming

    @property
    def callback_count(self) -> int:
        """Get the number of subscribed callbacks"""
        return len(self._activity_callbacks)
