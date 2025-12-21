"""
Activity screen for BBOT Server TUI
"""
from textual.app import ComposeResult
# Removed Screen import
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Static, Button
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual import work

from bbot_server.cli.tui.widgets.activity_feed import ActivityFeed
from bbot_server.cli.tui.widgets.filter_bar import FilterBar


class ActivityScreen(Container):
    """
    Live activity feed screen

    Displays real-time activity updates via WebSocket with
    filtering, pause/resume, and auto-scroll functionality.
    """


    is_streaming = reactive(False)
    is_paused = reactive(False)
    filter_type = reactive("")
    filter_host = reactive("")

    def __init__(self, app):
        super().__init__()
        self.bbot_app = app
        self._stream_worker = None
        self._start_timer = None
        self._has_loaded = False

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        with Container(id="activity-container"):
            # Controls at top
            with Horizontal(id="activity-controls"):
                yield FilterBar(placeholder="Filter activities...", id="activity-filter")
                yield Button("Pause", id="pause-btn", variant="warning")
                yield Button("Clear", id="clear-btn", variant="error")
                yield Button("Refresh", id="refresh-btn", variant="primary")

            # Status bar
            yield Static("[green]● LIVE[/green] Auto-scroll: ON", id="activity-status")

            # Activity feed
            with Vertical(id="activity-feed-container"):
                yield ActivityFeed(max_activities=1000, id="activity-feed")


    async def on_mount(self) -> None:
        """Called when screen is mounted - don't start streaming yet"""
        pass

    async def load_initial_data(self) -> None:
        """Start streaming on first visit to this tab"""
        if self._has_loaded:
            return

        self._has_loaded = True

        # Start trying to stream (will retry if services not ready)
        self._start_timer = self.set_interval(1.0, self._try_start_streaming)

    async def on_unmount(self) -> None:
        """Called when screen is unmounted - stop streaming"""
        # Stop the start timer
        if self._start_timer:
            self._start_timer.stop()

        # Stop streaming
        await self.stop_streaming()

    async def _try_start_streaming(self) -> None:
        """Try to start streaming, stop trying once successful"""
        if not self.is_streaming and self.bbot_app.websocket_service:
            await self.start_streaming()
            # Stop trying once we've started
            if self.is_streaming and self._start_timer:
                self._start_timer.stop()

    async def start_streaming(self) -> None:
        """Start WebSocket activity streaming"""
        if self.is_streaming:
            return

        # Check if services are initialized
        if not self.bbot_app.websocket_service:
            return

        self.is_streaming = True

        # Start the streaming worker (decorated with @work, so call it directly)
        self._stream_worker = self.stream_activities()

        # Update status
        self.update_status()

    async def stop_streaming(self) -> None:
        """Stop WebSocket activity streaming"""
        self.is_streaming = False

        # Cancel the worker and wait for it to finish
        if self._stream_worker and not self._stream_worker.is_finished:
            self._stream_worker.cancel()
            try:
                await self._stream_worker.wait()
            except Exception:
                pass  # Expected - worker was cancelled

        # Update status (only if screen is still mounted)
        try:
            self.update_status()
        except Exception:
            # Widget may not exist if we're unmounting
            pass

    @work(exclusive=True)
    async def stream_activities(self) -> None:
        """
        Worker that streams activities via WebSocket

        Runs in background and adds activities to the feed as they arrive.
        """
        try:
            # Get the async generator
            activity_stream = self.bbot_app.websocket_service.tail_activities(n=100)

            # Stream activities with WebSocket (gets last 100 historic)
            async for activity in activity_stream:
                if not self.is_streaming:
                    break

                # Add to feed (with error handling for unmounted widgets)
                try:
                    feed = self.query_one("#activity-feed", ActivityFeed)
                    feed.add_activity(activity)
                except Exception:
                    # Widget doesn't exist (screen unmounted)
                    break

        except Exception as e:
            # Show error in status (with error handling)
            try:
                status = self.query_one("#activity-status", Static)
                status.update(f"[red]● ERROR: {e}[/red]")
            except Exception:
                pass

            # Notify user
            try:
                self.notify(f"Activity stream error: {e}", severity="error", timeout=5)
            except Exception:
                pass

            # Mark as not streaming
            self.is_streaming = False

    def action_toggle_pause(self) -> None:
        """Toggle pause state of the feed"""
        feed = self.query_one("#activity-feed", ActivityFeed)
        self.is_paused = feed.toggle_pause()

        # Update button
        pause_btn = self.query_one("#pause-btn", Button)
        if self.is_paused:
            pause_btn.label = "Resume"
            pause_btn.variant = "success"
        else:
            pause_btn.label = "Pause"
            pause_btn.variant = "warning"
            # Catchup with any missed activities
            feed.resume_and_catchup()

        # Update status
        self.update_status()

        # Notify
        if self.is_paused:
            self.notify("Activity feed paused", timeout=2)
        else:
            self.notify("Activity feed resumed", timeout=2)

    def action_clear_feed(self) -> None:
        """Clear the activity feed"""
        feed = self.query_one("#activity-feed", ActivityFeed)
        feed.clear_feed()
        self.notify("Activity feed cleared", timeout=2)

    async def action_refresh(self) -> None:
        """Restart the activity stream"""
        await self.stop_streaming()
        feed = self.query_one("#activity-feed", ActivityFeed)
        feed.clear_feed()
        await self.start_streaming()
        self.notify("Activity stream refreshed", timeout=2)

    def action_focus_filter(self) -> None:
        """Focus the filter input"""
        filter_bar = self.query_one("#activity-filter", FilterBar)
        filter_bar.focus()

    def action_clear_filter(self) -> None:
        """Clear the filter"""
        filter_bar = self.query_one("#activity-filter", FilterBar)
        filter_bar.clear_filter()
        self.filter_type = ""
        self.filter_host = ""

        # Reapply filter (now empty)
        feed = self.query_one("#activity-feed", ActivityFeed)
        feed.filter_activities()

    def on_filter_bar_filter_changed(self, event: FilterBar.FilterChanged) -> None:
        """Handle filter text changes"""
        # For now, just update filter text
        # More advanced filtering can be added later
        # (e.g., parse "type:NEW_FINDING host:example.com")
        pass

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "pause-btn":
            self.action_toggle_pause()
        elif event.button.id == "clear-btn":
            self.action_clear_feed()
        elif event.button.id == "refresh-btn":
            await self.action_refresh()

    def update_status(self) -> None:
        """Update the status bar"""
        try:
            status = self.query_one("#activity-status", Static)
        except Exception:
            # Widget doesn't exist (unmounting)
            return

        parts = []

        # Streaming status
        if self.is_streaming:
            if self.is_paused:
                parts.append("[yellow]● PAUSED[/yellow]")
            else:
                parts.append("[green]● LIVE[/green]")
        else:
            parts.append("[red]● OFFLINE[/red]")

        # Auto-scroll status and activity count
        try:
            feed = self.query_one("#activity-feed", ActivityFeed)
            if feed.is_auto_scrolling:
                parts.append("Auto-scroll: ON")
            else:
                parts.append("Auto-scroll: OFF")

            # Activity count
            parts.append(f"Activities: {feed.buffered_count}")
        except Exception:
            # Feed widget doesn't exist
            pass

        status.update(" | ".join(parts))
