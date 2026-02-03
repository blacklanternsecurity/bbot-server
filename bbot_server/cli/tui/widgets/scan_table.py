"""
Scan table widget for BBOT Server TUI
"""
from typing import List, Optional
from textual.widgets import DataTable
from textual.coordinate import Coordinate

from bbot_server.cli.tui.utils.formatters import (
    format_timestamp_short,
    format_duration_short,
)
from bbot_server.cli.tui.utils.colors import colorize_status


class ScanTable(DataTable):
    """
    DataTable widget for displaying BBOT scans

    Shows scan information in a sortable, selectable table with
    color-coded status indicators.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cursor_type = "row"
        self.zebra_stripes = True
        self._scans = []
        self._scan_id_map = {}  # Maps row keys to scan IDs

    def on_mount(self) -> None:
        """Setup table columns when mounted"""
        self.add_columns(
            "Name",
            "Status",
            "Target",
            "Preset",
            "Started",
            "Finished",
            "Duration",
            "ID"
        )

    def update_scans(self, scans: List) -> None:
        """
        Update the table with a new list of scans

        Args:
            scans: List of Scan models
        """
        # Remember the currently selected scan before clearing
        selected_scan_id = self.get_selected_scan_id()

        self._scans = scans
        self._scan_id_map.clear()
        self.clear()

        # Sort by creation time (newest first)
        sorted_scans = sorted(scans, key=lambda s: s['created'] or '', reverse=True)

        for scan in sorted_scans:
            name = scan['name'] or scan['id']
            status_val = scan['status']
            status = colorize_status(status_val, status_val)
            target = scan.get('target')
            target_name = target['name'] if target else '-'
            preset = scan.get('preset')
            preset_name = preset['name'] if preset else '-'
            started = format_timestamp_short(scan['started_at']) if scan['started_at'] else "-"
            finished = format_timestamp_short(scan['finished_at']) if scan['finished_at'] else "-"
            duration = format_duration_short(scan['duration_seconds']) if scan['duration_seconds'] else "-"
            scan_id = scan['id']

            # Add row
            row_key = self.add_row(
                name,
                status,
                target_name,
                preset_name,
                started,
                finished,
                duration,
                scan_id,
            )

            self._scan_id_map[row_key] = scan_id

        # Restore selection if the previously selected scan is still in the table
        if selected_scan_id:
            self._restore_selection(selected_scan_id)

    def get_selected_scan_id(self) -> Optional[str]:
        """
        Get the ID of the currently selected scan

        Returns:
            Scan ID or None if no selection
        """
        if self.cursor_coordinate == Coordinate(0, 0) and not self.row_count:
            return None

        try:
            row_key, _ = self.coordinate_to_cell_key(self.cursor_coordinate)
            return self._scan_id_map.get(row_key)
        except Exception:
            return None

    def get_scan_by_id(self, scan_id: str):
        for scan in self._scans:
            if scan['id'] == scan_id:
                return scan
        return None

    def get_selected_scan(self):
        """
        Get the currently selected scan model

        Returns:
            Scan model or None if no selection
        """
        scan_id = self.get_selected_scan_id()
        if scan_id:
            return self.get_scan_by_id(scan_id)
        return None

    @property
    def scan_count(self) -> int:
        """Get the number of scans in the table"""
        return len(self._scans)

    def _restore_selection(self, scan_id: str) -> None:
        """
        Restore selection to a specific scan after table refresh

        Args:
            scan_id: Scan ID to select
        """
        # Safety check: ensure table is not empty
        if self.row_count == 0:
            return

        # Find the row key for this scan ID
        for row_key, mapped_id in self._scan_id_map.items():
            if mapped_id == scan_id:
                # Find the row index for this key
                try:
                    row_index = list(self._scan_id_map.keys()).index(row_key)
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

