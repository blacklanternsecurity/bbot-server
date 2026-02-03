"""
Assets screen for BBOT Server TUI
"""
from textual.app import ComposeResult
# Removed Screen import
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, Button
from textual.reactive import reactive

from bbot_server.cli.tui.widgets.asset_table import AssetTable
from bbot_server.cli.tui.widgets.asset_detail import AssetDetail
from bbot_server.cli.tui.widgets.filter_bar import FilterBar
from bbot_server.cli.tui.widgets.paginated_table import PaginatedTableContainer


class AssetsScreen(Container):
    """Asset browser screen with filtering and details"""


    filter_text = reactive("")

    def __init__(self, app):
        super().__init__()
        self.bbot_app = app
        self._refresh_timer = None
        self._has_loaded = False

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        with Container(id="assets-container"):
            # Filter controls
            with Horizontal(id="asset-controls"):
                yield FilterBar(placeholder="Filter by domain or host...", id="asset-filter")
                yield Button("Refresh", id="refresh-btn", variant="primary")

            # Status bar
            yield Static("Loading assets...", id="assets-status")

            # Main content
            with Horizontal(id="assets-content"):
                with Vertical(id="assets-table-container"):
                    yield PaginatedTableContainer(
                        AssetTable(id="asset-table"),
                        auto_page_size=True,
                        id="asset-pagination"
                    )

                with Vertical(id="asset-detail-container"):
                    yield Static("[bold]Asset Details[/bold]", id="detail-header")
                    yield AssetDetail(id="asset-detail")


    async def on_mount(self) -> None:
        """Called when screen is mounted"""
        # Start periodic refresh (paused until first load)
        self._refresh_timer = self.set_interval(10.0, self.refresh_assets, pause=True)

    async def load_initial_data(self) -> None:
        """Load data on first visit to this tab"""
        if self._has_loaded:
            return

        self._has_loaded = True
        await self.refresh_assets(show_loading=True)

        # Resume periodic refresh
        if self._refresh_timer:
            self._refresh_timer.resume()

    async def on_unmount(self) -> None:
        """Called when screen is unmounted"""
        if self._refresh_timer:
            self._refresh_timer.stop()

    async def refresh_assets(self, show_loading: bool = False) -> None:
        """Fetch and display assets from server with pagination

        Args:
            show_loading: If True, show "Loading..." status message (for manual refreshes)
        """
        # Check if services are initialized
        if not self.bbot_app.data_service:
            return

        try:
            status = self.query_one("#assets-status", Static)
            # Only show loading message on initial load or manual refresh
            if show_loading:
                status.update("[cyan]Loading assets...[/cyan]")

            # Get pagination parameters
            pagination = self.query_one("#asset-pagination", PaginatedTableContainer)
            skip, limit = pagination.get_skip_limit()

            # Fetch assets with server-side pagination and search
            search_term = self.filter_text if self.filter_text else None
            assets, total = await self.bbot_app.data_service.get_assets_paginated(
                skip=skip, limit=limit, search=search_term
            )

            # Update pagination with total count
            pagination.total_items = total

            # Update table with current page of assets
            table = self.query_one("#asset-table", AssetTable)
            table.update_assets(assets)

            # Update status (pagination widget shows page info, status shows filter info)
            if total > 0:
                if self.filter_text:
                    status.update(f"[green]Filtered: {total} assets match[/green]")
                else:
                    status.update(f"[green]{total} total assets[/green]")
            else:
                status.update("[yellow]No assets found[/yellow]")

        except Exception as e:
            # Show error
            status = self.query_one("#assets-status", Static)
            status.update(f"[red]Error loading assets: {e}[/red]")

    def on_data_table_row_highlighted(self, event) -> None:
        """Handle row selection"""
        # Only handle events from the asset table
        if event.data_table.id != "asset-table":
            return

        table = self.query_one("#asset-table", AssetTable)
        asset = table.get_selected_asset()

        # Update detail panel
        detail = self.query_one("#asset-detail", AssetDetail)
        detail.update_asset(asset)

    def on_filter_bar_filter_changed(self, event: FilterBar.FilterChanged) -> None:
        """Handle filter text changes"""
        self.filter_text = event.filter_text
        # Reset to first page when filter changes
        pagination = self.query_one("#asset-pagination", PaginatedTableContainer)
        pagination.reset_to_first_page()
        # Trigger refresh with new filter (show loading since user-initiated)
        self.run_worker(self.refresh_assets(show_loading=True))

    def on_paginated_table_container_page_changed(
        self, event: PaginatedTableContainer.PageChanged
    ) -> None:
        """Handle page navigation"""
        self.run_worker(self.refresh_assets())

    def on_paginated_table_container_page_size_changed(
        self, event: PaginatedTableContainer.PageSizeChanged
    ) -> None:
        """Handle page size changes from auto-sizing"""
        # Refetch data with new page size
        self.run_worker(self.refresh_assets())


    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "refresh-btn":
            await self.action_refresh()

    async def action_refresh(self) -> None:
        """Refresh assets"""
        await self.refresh_assets(show_loading=True)
        self.notify("Assets refreshed", timeout=2)

    def action_focus_filter(self) -> None:
        """Focus the filter input"""
        filter_bar = self.query_one("#asset-filter", FilterBar)
        filter_bar.focus()

    def action_clear_filter(self) -> None:
        """Clear the filter"""
        filter_bar = self.query_one("#asset-filter", FilterBar)
        filter_bar.clear_filter()
        self.filter_text = ""
        # Reset pagination when filter is cleared
        pagination = self.query_one("#asset-pagination", PaginatedTableContainer)
        pagination.reset_to_first_page()
