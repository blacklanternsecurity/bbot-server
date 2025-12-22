"""
Target table widget for BBOT Server TUI
"""
from textual.widgets import DataTable
from bbot_server.cli.tui.utils.formatters import format_timestamp


class TargetTable(DataTable):
    """Table widget for displaying BBOT targets"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._targets = []

    def on_mount(self) -> None:
        """Setup table columns"""
        self.add_columns("Name", "Description", "Target Size", "Default", "Created")
        self.cursor_type = "row"
        self.zebra_stripes = True

    def update_targets(self, targets: list) -> None:
        """
        Update table with new targets

        Args:
            targets: List of Target models
        """
        self._targets = targets

        # Clear existing rows
        self.clear()

        # Add new rows
        for target in targets:
            name = getattr(target, 'name', 'UNKNOWN')
            description = getattr(target, 'description', '')
            # Truncate long descriptions
            if len(description) > 40:
                description = description[:37] + "..."

            target_size = str(getattr(target, 'target_size', 0))
            is_default = "Yes" if getattr(target, 'default', False) else ""
            created = format_timestamp(getattr(target, 'created', 0))

            self.add_row(name, description, target_size, is_default, created)

    def get_selected_target(self):
        """
        Get the currently selected target

        Returns:
            Target model or None
        """
        if self.cursor_row is None or self.cursor_row < 0:
            return None

        row_index = self.cursor_row
        if row_index < len(self._targets):
            return self._targets[row_index]

        return None
