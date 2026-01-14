"""
Asset table widget for BBOT Server TUI
"""
from typing import List, Optional
from textual.widgets import DataTable
from textual.coordinate import Coordinate

from bbot_server.cli.tui.utils.formatters import format_list, format_timestamp_short


class AssetTable(DataTable):
    """
    DataTable widget for displaying assets

    Shows asset information including hosts, ports, technologies,
    and findings in a sortable, filterable table.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cursor_type = "row"
        self.zebra_stripes = True
        self._assets = []
        self._asset_id_map = {}  # Maps row keys to asset hosts

    def on_mount(self) -> None:
        """Setup table columns when mounted"""
        self.add_columns(
            "Host",
            "Open Ports",
            "Technologies",
            "Cloud",
            "Findings",
            "Modified"
        )

    def update_assets(self, assets: List) -> None:
        """
        Update the table with a new list of assets

        Args:
            assets: List of Asset models
        """
        # Remember the currently selected host before clearing
        selected_host = self.get_selected_host()

        self._assets = assets
        self._asset_id_map.clear()
        self.clear()

        # Sort by modification time (newest first)
        sorted_assets = sorted(assets, key=lambda a: getattr(a, 'modified', 0), reverse=True)

        for asset in sorted_assets:
            # Format the data
            host = getattr(asset, 'host', 'unknown')

            # Open ports
            if hasattr(asset, 'open_ports') and asset.open_ports:
                ports = format_list(sorted([str(p) for p in asset.open_ports]), max_items=5)
            else:
                ports = "-"

            # Technologies
            if hasattr(asset, 'technologies') and asset.technologies:
                techs = format_list(sorted(asset.technologies), max_items=3)
            else:
                techs = "-"

            # Cloud providers
            if hasattr(asset, 'cloud') and asset.cloud:
                cloud = format_list(sorted(asset.cloud), max_items=2)
            else:
                cloud = "-"

            # Findings count
            if hasattr(asset, 'findings') and asset.findings:
                findings = str(len(asset.findings))
            else:
                findings = "0"

            # Last modified
            if hasattr(asset, 'modified') and asset.modified:
                modified = format_timestamp_short(asset.modified)
            else:
                modified = "-"

            # Add row
            row_key = self.add_row(
                host,
                ports,
                techs,
                cloud,
                findings,
                modified
            )

            # Map row key to host for later lookup
            self._asset_id_map[row_key] = host

        # Restore selection if the previously selected host is still in the table
        if selected_host:
            self._restore_selection(selected_host)

    def get_selected_host(self) -> Optional[str]:
        """
        Get the host of the currently selected asset

        Returns:
            Host string or None if no selection
        """
        if self.cursor_coordinate == Coordinate(0, 0) and not self.row_count:
            return None

        try:
            row_key, _ = self.coordinate_to_cell_key(self.cursor_coordinate)
            return self._asset_id_map.get(row_key)
        except Exception:
            return None

    def get_asset_by_host(self, host: str):
        """
        Get an asset model by host

        Args:
            host: Host string

        Returns:
            Asset model or None if not found
        """
        for asset in self._assets:
            if getattr(asset, 'host', None) == host:
                return asset
        return None

    def get_selected_asset(self):
        """
        Get the currently selected asset model

        Returns:
            Asset model or None if no selection
        """
        host = self.get_selected_host()
        if host:
            return self.get_asset_by_host(host)
        return None

    @property
    def asset_count(self) -> int:
        """Get the number of assets in the table"""
        return len(self._assets)

    def _restore_selection(self, host: str) -> None:
        """
        Restore selection to a specific host after table refresh

        Args:
            host: Host string to select
        """
        # Safety check: ensure table is not empty
        if self.row_count == 0:
            return

        # Find the row key for this host
        for row_key, mapped_host in self._asset_id_map.items():
            if mapped_host == host:
                # Find the row index for this key
                try:
                    row_index = list(self._asset_id_map.keys()).index(row_key)
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
