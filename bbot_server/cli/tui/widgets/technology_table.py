"""
Technology table widget for BBOT Server TUI
"""
from textual.widgets import DataTable
from bbot_server.cli.tui.utils.formatters import format_timestamp


class TechnologyTable(DataTable):
    """Table widget for displaying BBOT technologies"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._technologies = []

    def on_mount(self) -> None:
        """Setup table columns"""
        self.add_columns("Technology", "Host", "Port", "Last Seen")
        self.cursor_type = "row"
        self.zebra_stripes = True

    def update_technologies(self, technologies: list) -> None:
        """
        Update table with new technologies

        Args:
            technologies: List of Technology models
        """
        # Remember the currently selected row index before clearing
        selected_row = self.cursor_row if self.cursor_row >= 0 else 0

        self._technologies = technologies

        # Clear existing rows
        self.clear()

        # Add new rows
        for tech in technologies:
            technology = tech.get('technology', 'UNKNOWN')
            # Truncate long technology names
            if len(technology) > 50:
                technology = technology[:47] + "..."

            host = tech.get('host', '')
            port = str(tech.get('port', ''))
            last_seen = format_timestamp(tech.get('last_seen', 0))

            self.add_row(technology, host, port, last_seen)

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

    def get_selected_technology(self):
        """
        Get the currently selected technology

        Returns:
            Technology model or None
        """
        if self.cursor_row is None or self.cursor_row < 0:
            return None

        row_index = self.cursor_row
        if row_index < len(self._technologies):
            return self._technologies[row_index]

        return None
