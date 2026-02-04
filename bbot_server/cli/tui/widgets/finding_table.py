"""
Finding table widget for BBOT Server TUI
"""

from typing import List, Optional
from textual.widgets import DataTable
from textual.coordinate import Coordinate

from bbot_server.cli.tui.utils.formatters import format_timestamp_short, truncate_string
from bbot_server.cli.tui.utils.colors import colorize_severity, get_severity_score


class FindingTable(DataTable):
    """DataTable widget for displaying security findings"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cursor_type = "row"
        self.zebra_stripes = True
        self._findings = []
        self._finding_id_map = {}

    def on_mount(self) -> None:
        """Setup table columns"""
        self.add_columns("Severity", "Name", "Host", "Description", "Last Seen")

    def update_findings(self, findings: List) -> None:
        """Update table with findings"""
        # Remember the currently selected finding before clearing
        selected_finding_id = self.get_selected_finding_id()

        self._findings = findings
        self._finding_id_map.clear()
        self.clear()

        # Sort by severity (highest first), then by timestamp
        def sort_key(f):
            sev = f.get("severity", "INFO")
            mod = f.get("modified", 0) or 0
            return (-get_severity_score(sev), -mod)

        sorted_findings = sorted(findings, key=sort_key)

        for finding in sorted_findings:
            severity_value = finding.get("severity", "INFO")
            severity = colorize_severity(severity_value, severity_value)
            name = finding.get("name", "-") or "-"
            host = finding.get("host", "-") or "-"
            description_text = finding.get("description", "-") or "-"
            description = truncate_string(description_text, 60) if description_text != "-" else "-"

            modified = finding.get("modified")
            last_seen = format_timestamp_short(modified) if modified else "-"

            row_key = self.add_row(severity, name, host, description, last_seen)

            finding_id = finding.get("id")
            if finding_id:
                self._finding_id_map[row_key] = finding_id

        # Restore selection if the previously selected finding is still in the table
        if selected_finding_id:
            self._restore_selection(selected_finding_id)

    def get_selected_finding_id(self) -> Optional[str]:
        """Get ID of selected finding"""
        if self.cursor_coordinate == Coordinate(0, 0) and not self.row_count:
            return None

        try:
            row_key, _ = self.coordinate_to_cell_key(self.cursor_coordinate)
            return self._finding_id_map.get(row_key)
        except Exception:
            return None

    def get_finding_by_id(self, finding_id: str):
        """Get finding by ID"""
        for finding in self._findings:
            if finding.get("id") == finding_id:
                return finding
        return None

    def get_selected_finding(self):
        """Get selected finding model"""
        finding_id = self.get_selected_finding_id()
        if finding_id:
            return self.get_finding_by_id(finding_id)
        return None

    @property
    def finding_count(self) -> int:
        """Get number of findings"""
        return len(self._findings)

    def _restore_selection(self, finding_id: str) -> None:
        """
        Restore selection to a specific finding after table refresh

        Args:
            finding_id: Finding ID to select
        """
        # Safety check: ensure table is not empty
        if self.row_count == 0:
            return

        # Find the row key for this finding ID
        for row_key, mapped_id in self._finding_id_map.items():
            if mapped_id == finding_id:
                # Find the row index for this key
                try:
                    row_index = list(self._finding_id_map.keys()).index(row_key)
                    # Additional safety: ensure row_index is within bounds
                    if 0 <= row_index < self.row_count:
                        self.move_cursor(row=row_index, column=0)
                    break
                except (ValueError, Exception):
                    pass

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
