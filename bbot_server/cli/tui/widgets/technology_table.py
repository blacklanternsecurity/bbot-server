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
        self._technologies = technologies

        # Clear existing rows
        self.clear()

        # Add new rows
        for tech in technologies:
            technology = getattr(tech, 'technology', 'UNKNOWN')
            # Truncate long technology names
            if len(technology) > 50:
                technology = technology[:47] + "..."

            host = getattr(tech, 'host', '')
            port = str(getattr(tech, 'port', ''))
            last_seen = format_timestamp(getattr(tech, 'last_seen', 0))

            self.add_row(technology, host, port, last_seen)

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
