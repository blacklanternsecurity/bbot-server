"""
Assets screen for BBOT Server TUI
"""
from textual.app import ComposeResult
# Removed Screen import
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Static, Button
from textual.binding import Binding
from textual.css.query import NoMatches
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
        self._cached_assets = []  # Cache all assets to avoid refetching on page changes

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
                        items_per_page=self.bbot_app.items_per_page,
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
        """Fetch and cache all assets from server

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

            # Fetch ALL assets and cache them (no skip/limit)
            self._cached_assets = await self.bbot_app.data_service.list_assets()

            # Update table from cache
            self._update_table_from_cache()

        except Exception as e:
            # Show error
            try:
                status = self.query_one("#assets-status", Static)
                status.update(f"[red]Error loading assets: {e}[/red]")
            except:
                pass

    def _update_table_from_cache(self) -> None:
        """Update table display from cached data (for page changes without refetching)"""
        try:
            # Apply client-side filters
            filtered_assets = self._cached_assets

            # Apply domain filter if present
            if self.filter_text:
                filter_lower = self.filter_text.lower()
                filtered_assets = [
                    a for a in self._cached_assets
                    if filter_lower in getattr(a, 'host', '').lower()
                    or filter_lower in getattr(a, 'domain', '').lower()
                ]

            # Get pagination container
            pagination = self.query_one("#asset-pagination", PaginatedTableContainer)
            skip, limit = pagination.get_skip_limit()

            # Apply pagination to filtered results
            paginated_assets = filtered_assets[skip:skip + limit]

            # Update table with paginated subset
            table = self.query_one("#asset-table", AssetTable)
            table.update_assets(paginated_assets)

            # Update pagination total_items (using filtered count)
            pagination.total_items = len(filtered_assets)

            # Update status
            status = self.query_one("#assets-status", Static)
            if paginated_assets:
                if self.filter_text:
                    status.update(f"[green]Showing {len(paginated_assets)} of {len(filtered_assets)} filtered assets[/green]")
                else:
                    status.update(f"[green]Showing {len(paginated_assets)} assets[/green]")
            else:
                status.update("[yellow]No assets found[/yellow]")

        except Exception:
            pass

    def on_paginated_table_container_page_changed(self, message: PaginatedTableContainer.PageChanged) -> None:
        """Handle page changes - update from cache without refetching"""
        self._update_table_from_cache()

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
        try:
            pagination = self.query_one("#asset-pagination", PaginatedTableContainer)
            pagination.reset_to_first_page()
        except Exception:
            pass
        # Trigger refresh with new filter (show loading since user-initiated)
        self.run_worker(self.refresh_assets(show_loading=True))


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
