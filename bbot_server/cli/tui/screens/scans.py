"""
Scans screen for BBOT Server TUI
"""
from textual.app import ComposeResult
# Removed Screen import
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Static, Button
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.reactive import reactive

from bbot_server.cli.tui.widgets.scan_table import ScanTable
from bbot_server.cli.tui.widgets.scan_detail import ScanDetail
from bbot_server.cli.tui.widgets.filter_bar import FilterBar
from bbot_server.cli.tui.widgets.paginated_table import PaginatedTableContainer


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
        self._cached_scans = []  # Cache all scans to avoid refetching on page changes

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        with Container(id="scans-container"):
            # Filter bar at top
            with Horizontal(id="filter-container"):
                yield FilterBar(placeholder="Filter by scan name or target...", id="scan-filter")
                yield Button("Refresh", id="refresh-btn", variant="primary")
                yield Button("New Scan", id="new-scan-btn", variant="success")

            # Status bar
            yield Static("Loading scans...", id="scans-status")

            # Main content: table on left, detail on right
            with Horizontal(id="scans-content"):
                with Vertical(id="scans-table-container"):
                    yield PaginatedTableContainer(
                        ScanTable(id="scan-table"),
                        items_per_page=self.bbot_app.items_per_page,
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
        """Fetch and cache all scans from server

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
                status.update("[cyan]Loading scans...[/cyan]")

            # Fetch ALL scans and cache them
            self._cached_scans = await self.bbot_app.data_service.get_scans()

            # Update table from cache
            self._update_table_from_cache()

        except Exception as e:
            # Show error
            try:
                status = self.query_one("#scans-status", Static)
                status.update(f"[red]Error loading scans: {e}[/red]")
            except:
                pass

    def _update_table_from_cache(self) -> None:
        """Update table display from cached data (for page changes without refetching)"""
        try:
            # Apply client-side filter if any
            filtered_scans = self._cached_scans
            if self.filter_text:
                filter_lower = self.filter_text.lower()
                filtered_scans = [
                    s for s in self._cached_scans
                    if filter_lower in getattr(s, 'name', '').lower()
                    or filter_lower in ' '.join(getattr(s, 'targets', [])).lower()
                ]

            # Get pagination container
            pagination = self.query_one("#scan-pagination", PaginatedTableContainer)
            skip, limit = pagination.get_skip_limit()

            # Apply pagination to filtered results
            paginated_scans = filtered_scans[skip:skip + limit]

            # Update table with paginated subset
            table = self.query_one("#scan-table", ScanTable)
            table.update_scans(paginated_scans)

            # Update pagination total_items (using filtered count)
            pagination.total_items = len(filtered_scans)

            # Update status
            status = self.query_one("#scans-status", Static)
            if paginated_scans:
                if self.filter_text:
                    status.update(f"[green]Showing {len(paginated_scans)} of {len(filtered_scans)} filtered scans[/green]")
                else:
                    status.update(f"[green]Showing {len(paginated_scans)} scans[/green]")
            else:
                status.update("[yellow]No scans found[/yellow]")

        except Exception:
            pass

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
            self.selected_scan_id = scan.id

    def on_paginated_table_container_page_changed(self, message: PaginatedTableContainer.PageChanged) -> None:
        """Handle page changes - update from cache without refetching"""
        self._update_table_from_cache()

    def on_filter_bar_filter_changed(self, event: FilterBar.FilterChanged) -> None:
        """Handle filter text changes"""
        self.filter_text = event.filter_text
        # Reset to first page when filter changes
        try:
            pagination = self.query_one("#scan-pagination", PaginatedTableContainer)
            pagination.reset_to_first_page()
        except Exception:
            pass
        # Trigger refresh with new filter (show loading since user-initiated)
        self.run_worker(self.refresh_scans(show_loading=True))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "refresh-btn":
            await self.action_refresh()
        elif event.button.id == "new-scan-btn":
            await self.action_new_scan()

    async def action_refresh(self) -> None:
        """Refresh scans"""
        await self.refresh_scans(show_loading=True)
        self.notify("Scans refreshed", timeout=2)

    async def action_new_scan(self) -> None:
        """Create a new scan"""
        # TODO: Implement scan creation modal in Phase 7+
        self.notify("Scan creation coming soon!", severity="information", timeout=3)

    async def action_cancel_scan(self) -> None:
        """Cancel the selected scan"""
        table = self.query_one("#scan-table", ScanTable)
        scan = table.get_selected_scan()

        if not scan:
            self.notify("No scan selected", severity="warning", timeout=2)
            return

        # Check if scan is running
        if scan.status not in ["RUNNING", "QUEUED", "STARTING"]:
            self.notify(f"Cannot cancel scan with status: {scan.status}",
                       severity="warning", timeout=3)
            return

        try:
            # Cancel via data service
            success = await self.bbot_app.data_service.cancel_scan(scan.id)

            if success:
                self.notify(f"Cancelled scan: {scan.name}", timeout=3)
                # Refresh to show updated status
                await self.refresh_scans()
            else:
                self.notify("Failed to cancel scan", severity="error", timeout=3)

        except Exception as e:
            self.notify(f"Error cancelling scan: {e}", severity="error", timeout=5)

    def action_focus_filter(self) -> None:
        """Focus the filter input"""
        filter_bar = self.query_one("#scan-filter", FilterBar)
        filter_bar.focus()

    def action_clear_filter(self) -> None:
        """Clear the filter"""
        filter_bar = self.query_one("#scan-filter", FilterBar)
        filter_bar.clear_filter()
        self.filter_text = ""
        # Trigger refresh to show all scans
        self.run_worker(self.refresh_scans())
