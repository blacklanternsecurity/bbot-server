"""
Event table widget for BBOT Server TUI
"""

from textual.widgets import DataTable
from bbot_server.cli.tui.utils.formatters import format_timestamp


class EventTable(DataTable):
    """Table widget for displaying BBOT events"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._events = []

    def on_mount(self) -> None:
        """Setup table columns"""
        self.add_columns("Type", "Data", "Host", "Scan", "Timestamp")
        self.cursor_type = "row"
        self.zebra_stripes = True

    def update_events(self, events: list) -> None:
        """
        Update table with new events

        Args:
            events: List of event dictionaries
        """
        # Remember the currently selected row index before clearing
        selected_row = self.cursor_row if self.cursor_row >= 0 else 0

        self._events = events

        # Clear existing rows
        self.clear()

        # Add new rows
        for event in events:
            event_type = event.get("type", "UNKNOWN")
            data = str(event.get("data", ""))
            # Truncate long data
            if len(data) > 50:
                data = data[:47] + "..."
            host = event.get("host", "")
            scan_id = event.get("scan", "")
            # Truncate scan ID
            if len(scan_id) > 8:
                scan_id = scan_id[:8]
            timestamp = format_timestamp(event.get("timestamp", 0))

            self.add_row(event_type, data, host, scan_id, timestamp)

        # Restore selection to the same row index (or closest available)
        if self.row_count > 0:
            restore_row = min(selected_row, self.row_count - 1)
            self.move_cursor(row=restore_row, column=0)

    def on_key(self, event) -> None:
        """Handle key events for circular navigation"""
        if event.key == "up":
            # If on first row, wrap to last row
            if self.cursor_row == 0 and self.row_count > 0:
                self.move_cursor(row=self.row_count - 1, column=0)
                event.prevent_default()
                event.stop()
        elif event.key == "down":
            # If on last row, wrap to first row
            if self.cursor_row == self.row_count - 1 and self.row_count > 0:
                self.move_cursor(row=0, column=0)
                event.prevent_default()
                event.stop()

    def get_selected_event(self):
        """
        Get the currently selected event

        Returns:
            Event dict or None
        """
        if not self.cursor_row or self.cursor_row < 0:
            return None

        row_index = self.cursor_row
        if row_index < len(self._events):
            return self._events[row_index]

        return None
