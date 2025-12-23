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
        # Remember the currently selected row index before clearing
        selected_row = self.cursor_row if self.cursor_row >= 0 else 0

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
