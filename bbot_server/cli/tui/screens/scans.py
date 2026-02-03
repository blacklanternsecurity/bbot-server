"""
Scans screen for BBOT Server TUI
"""
from textual.app import ComposeResult
# Removed Screen import
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, Button
from textual.reactive import reactive

from bbot_server.cli.tui.widgets.scan_table import ScanTable
from bbot_server.cli.tui.widgets.scan_detail import ScanDetail
from bbot_server.cli.tui.widgets.filter_bar import FilterBar
from bbot_server.cli.tui.widgets.paginated_table import PaginatedTableContainer
from bbot_server.cli.tui.utils.colors import (
    loading_text, success_text, warning_text, error_text
)


class ScansScreen(Container):
    """
    Scan management screen

    Displays a table of all scans with filtering, details panel,
    and actions for creating, cancelling, and refreshing scans.
    """


    filter_text = reactive("")
    selected_scan_id = reactive(None)

    def __init__(self, app):
        super().__init__()
        self.bbot_app = app
        self._refresh_timer = None
        self._has_loaded = False

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        with Container(id="scans-container"):
            # Filter bar at top
            with Horizontal(id="filter-container"):
                yield FilterBar(placeholder="Filter by scan name or target...", id="scan-filter")
                yield Button("Refresh", id="refresh-btn", variant="primary")

            # Status bar
            yield Static("Loading scans...", id="scans-status")

            # Main content: table on left, detail on right
            with Horizontal(id="scans-content"):
                with Vertical(id="scans-table-container"):
                    yield PaginatedTableContainer(
                        ScanTable(id="scan-table"),
                        auto_page_size=True,
                        id="scan-pagination"
                    )

                with Vertical(id="scan-detail-container"):
                    yield Static("[bold]Scan Details[/bold]", id="detail-header")
                    yield ScanDetail(id="scan-detail")


    async def on_mount(self) -> None:
        """Called when screen is mounted"""
        # Start periodic refresh (paused until first load)
        self._refresh_timer = self.set_interval(5.0, self.refresh_scans, pause=True)

    async def load_initial_data(self) -> None:
        """Load data on first visit to this tab"""
        if self._has_loaded:
            return

        self._has_loaded = True
        await self.refresh_scans(show_loading=True)

        # Resume periodic refresh
        if self._refresh_timer:
            self._refresh_timer.resume()

    async def on_unmount(self) -> None:
        """Called when screen is unmounted"""
        # Stop periodic refresh
        if self._refresh_timer:
            self._refresh_timer.stop()

    async def refresh_scans(self, show_loading: bool = False) -> None:
        """Fetch and display scans from server with pagination

        Args:
            show_loading: If True, show "Loading..." status message (for manual refreshes)
        """
        # Check if services are initialized
        if not self.bbot_app.data_service:
            return

        try:
            status = self.query_one("#scans-status", Static)
            # Only show loading message on initial load or manual refresh
            if show_loading:
                status.update(loading_text("Loading scans..."))

            # Get pagination parameters
            pagination = self.query_one("#scan-pagination", PaginatedTableContainer)
            skip, limit = pagination.get_skip_limit()

            # Fetch scans with server-side pagination and search
            scans, total = await self.bbot_app.data_service.get_scans_paginated(
                skip=skip, limit=limit, search=self.filter_text or None
            )

            # Update pagination with total count
            pagination.total_items = total

            # Update table with current page of scans
            table = self.query_one("#scan-table", ScanTable)
            table.update_scans(scans)

            # Update status (pagination widget shows page info, status shows filter info)
            if total > 0:
                if self.filter_text:
                    status.update(success_text(f"Filtered: {total} scans match"))
                else:
                    status.update(success_text(f"{total} total scans"))
            else:
                status.update(warning_text("No scans found"))

        except Exception as e:
            # Show error
            status = self.query_one("#scans-status", Static)
            status.update(error_text(f"Error loading scans: {e}"))

    def on_data_table_row_highlighted(self, event) -> None:
        """Handle row selection in scan table"""
        # Only handle events from the scan table
        if event.data_table.id != "scan-table":
            return

        table = self.query_one("#scan-table", ScanTable)
        scan = table.get_selected_scan()

        # Update detail panel
        detail = self.query_one("#scan-detail", ScanDetail)
        detail.update_scan(scan)

        # Update selected scan ID
        if scan:
            self.selected_scan_id = scan['id']

    def on_filter_bar_filter_changed(self, event: FilterBar.FilterChanged) -> None:
        """Handle filter text changes"""
        self.filter_text = event.filter_text
        # Reset to first page when filter changes
        pagination = self.query_one("#scan-pagination", PaginatedTableContainer)
        pagination.reset_to_first_page()
        # Trigger refresh with new filter (show loading since user-initiated)
        self.run_worker(self.refresh_scans(show_loading=True))

    def on_paginated_table_container_page_changed(
        self, event: PaginatedTableContainer.PageChanged
    ) -> None:
        """Handle page navigation"""
        self.run_worker(self.refresh_scans())

    def on_paginated_table_container_page_size_changed(
        self, event: PaginatedTableContainer.PageSizeChanged
    ) -> None:
        """Handle page size changes from auto-sizing"""
        # Refetch data with new page size
        self.run_worker(self.refresh_scans())

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "refresh-btn":
            await self.action_refresh()

    async def action_refresh(self) -> None:
        """Refresh scans"""
        await self.refresh_scans(show_loading=True)
        self.notify("Scans refreshed", timeout=2)

    def action_focus_filter(self) -> None:
        """Focus the filter input"""
        filter_bar = self.query_one("#scan-filter", FilterBar)
        filter_bar.focus()

    def action_clear_filter(self) -> None:
        """Clear the filter"""
        filter_bar = self.query_one("#scan-filter", FilterBar)
        filter_bar.clear_filter()
        self.filter_text = ""
        # Reset pagination when filter is cleared
        pagination = self.query_one("#scan-pagination", PaginatedTableContainer)
        pagination.reset_to_first_page()
        # Trigger refresh to show all scans
        self.run_worker(self.refresh_scans())
