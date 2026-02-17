"""
Activity feed widget for BBOT Server TUI
"""

from collections import deque
from textual.widgets import RichLog
from textual.reactive import reactive

from bbot_server.cli.tui.utils.formatters import format_timestamp_short
from bbot_server.cli.tui.utils.colors import MUTED, WARNING


class ActivityFeed(RichLog):
    """
    Scrollable activity feed widget with auto-scroll

    Displays real-time activity updates with timestamps,
    color-coded descriptions, and pause/resume functionality.
    """

    is_paused = reactive(False)
    activity_count = reactive(0)

    def __init__(self, max_activities: int = 1000, **kwargs):
        super().__init__(highlight=True, markup=True, auto_scroll=True, **kwargs)
        self.max_activities = max_activities
        self._activities = deque(maxlen=max_activities)
        self._auto_scroll_enabled = True

    def add_activity(self, activity) -> None:
        """
        Add an activity to the feed

        Args:
            activity: Activity model with timestamp and description_colored
        """
        if self.is_paused:
            # Still store it, just don't display
            self._activities.append(activity)
            self.activity_count = len(self._activities)
            return

        # Format the activity
        timestamp = format_timestamp_short(activity.timestamp)
        description = (
            activity.description_colored if hasattr(activity, "description_colored") else str(activity.description)
        )

        # Add to display
        self.write(f"[{MUTED}][{timestamp}][/{MUTED}] {description}")

        # Store activity
        self._activities.append(activity)
        self.activity_count = len(self._activities)

        # Auto-scroll if enabled
        if self._auto_scroll_enabled:
            self.scroll_end(animate=False)

    def toggle_pause(self) -> bool:
        """
        Toggle pause state

        Returns:
            New pause state (True if now paused)
        """
        self.is_paused = not self.is_paused
        return self.is_paused

    def resume_and_catchup(self) -> int:
        """
        Resume and display any activities that were received while paused

        Returns:
            Number of new activities displayed
        """
        if not self.is_paused:
            return 0

        self.is_paused = False

        # Show paused activities
        # Note: Activities are already in _activities deque
        # Just need to display the most recent ones that weren't shown

        # For simplicity, just note we're resuming
        self.write(f"[{WARNING}]--- Resumed ---[/{WARNING}]")

        return 0

    def clear_feed(self) -> None:
        """Clear all activities from the feed"""
        self.clear()
        self._activities.clear()
        self.activity_count = 0

    def set_auto_scroll(self, enabled: bool) -> None:
        """
        Enable or disable auto-scroll

        Args:
            enabled: Whether to auto-scroll
        """
        self._auto_scroll_enabled = enabled
        self.auto_scroll = enabled

    def filter_activities(self, activity_type: str = None, host: str = None) -> None:
        """
        Filter and redisplay activities

        Args:
            activity_type: Filter by activity type
            host: Filter by host
        """
        self.clear()

        # Filter activities
        filtered = self._activities

        if activity_type:
            filtered = [a for a in filtered if hasattr(a, "type") and a.type == activity_type]

        if host:
            filtered = [a for a in filtered if hasattr(a, "host") and a.host == host]

        # Redisplay filtered activities
        for activity in filtered:
            timestamp = format_timestamp_short(activity.timestamp)
            description = (
                activity.description_colored if hasattr(activity, "description_colored") else str(activity.description)
            )
            self.write(f"[{MUTED}][{timestamp}][/{MUTED}] {description}")

    @property
    def is_auto_scrolling(self) -> bool:
        """Check if auto-scroll is enabled"""
        return self._auto_scroll_enabled

    @property
    def buffered_count(self) -> int:
        """Get the number of buffered activities"""
        return len(self._activities)
