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
            events: List of Event models
        """
        self._events = events

        # Clear existing rows
        self.clear()

        # Add new rows
        for event in events:
            event_type = getattr(event, 'type', 'UNKNOWN')
            data = str(getattr(event, 'data', ''))
            # Truncate long data
            if len(data) > 50:
                data = data[:47] + "..."
            host = getattr(event, 'host', '')
            scan_id = getattr(event, 'scan', '')
            # Truncate scan ID
            if len(scan_id) > 8:
                scan_id = scan_id[:8]
            timestamp = format_timestamp(getattr(event, 'timestamp', 0))

            self.add_row(event_type, data, host, scan_id, timestamp)

    def get_selected_event(self):
        """
        Get the currently selected event

        Returns:
            Event model or None
        """
        if not self.cursor_row or self.cursor_row < 0:
            return None

        row_index = self.cursor_row
        if row_index < len(self._events):
            return self._events[row_index]

        return None
