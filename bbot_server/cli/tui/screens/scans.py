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
                yield FilterBar(placeholder="Filter scans...", id="scan-filter")
                yield Button("Refresh", id="refresh-btn", variant="primary")
                yield Button("New Scan", id="new-scan-btn", variant="success")

            # Main content: table on left, detail on right
            with Horizontal(id="scans-content"):
                with Vertical(id="scans-table-container"):
                    yield Static("Loading scans...", id="scans-status")
                    yield ScanTable(id="scan-table")

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
        await self.refresh_scans()

        # Resume periodic refresh
        if self._refresh_timer:
            self._refresh_timer.resume()

    async def on_unmount(self) -> None:
        """Called when screen is unmounted"""
        # Stop periodic refresh
        if self._refresh_timer:
            self._refresh_timer.stop()

    async def refresh_scans(self) -> None:
        """Fetch and display scans from the server"""
        # Check if services are initialized
        if not self.bbot_app.data_service:
            return

        try:
            # Show loading status
            status = self.query_one("#scans-status", Static)
            status.update("[cyan]Loading scans...[/cyan]")

            # Fetch scans via data service
            scans = await self.bbot_app.data_service.get_scans()

            # Update table
            table = self.query_one("#scan-table", ScanTable)
            table.update_scans(scans)

            # Update status
            if scans:
                status.update(f"[green]Loaded {len(scans)} scans[/green]")
            else:
                status.update("[yellow]No scans found[/yellow]")

            # Apply current filter if any
            if self.filter_text:
                table.filter_scans(self.filter_text)

        except Exception as e:
            # Show error
            status = self.query_one("#scans-status", Static)
            status.update(f"[red]Error loading scans: {e}[/red]")
            self.notify(f"Failed to load scans: {e}", severity="error", timeout=5)

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

    def on_filter_bar_filter_changed(self, event: FilterBar.FilterChanged) -> None:
        """Handle filter text changes"""
        self.filter_text = event.filter_text

        # Apply filter to table
        table = self.query_one("#scan-table", ScanTable)
        table.filter_scans(self.filter_text)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "refresh-btn":
            await self.action_refresh()
        elif event.button.id == "new-scan-btn":
            await self.action_new_scan()

    async def action_refresh(self) -> None:
        """Refresh scans"""
        await self.refresh_scans()
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

        # Reapply filter (now empty) to show all scans
        table = self.query_one("#scan-table", ScanTable)
        table.filter_scans("")
