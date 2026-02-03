"""
Assets screen for BBOT Server TUI
"""
from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Static, Button, Checkbox
from textual.binding import Binding
from textual.reactive import reactive

from bbot_server.cli.tui.widgets.asset_table import AssetTable
from bbot_server.cli.tui.widgets.asset_detail import AssetDetail
from bbot_server.cli.tui.widgets.filter_bar import FilterBar


class AssetsScreen(Screen):
    """Asset browser screen with filtering and details"""

    BINDINGS = [
        Binding("d", "app.show_dashboard", "Dashboard"),
        Binding("s", "app.show_scans", "Scans"),
        Binding("a", "app.show_assets", "Assets"),
        Binding("f", "app.show_findings", "Findings"),
        Binding("v", "app.show_activity", "Activity"),
        Binding("g", "app.show_agents", "Agents"),
        Binding('r', 'refresh', 'Refresh'),
        Binding('i', 'toggle_in_scope', 'In-Scope'),
        Binding('q', 'app.quit', 'Quit'),
    ]

    filter_text = reactive("")
    in_scope_only = reactive(False)

    def __init__(self, app):
        super().__init__()
        self.bbot_app = app
        self._refresh_timer = None

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        with Container(id="assets-container"):
            # Filter controls
            with Horizontal(id="asset-controls"):
                yield FilterBar(placeholder="Filter by domain or host...", id="asset-filter")
                yield Checkbox("In-Scope Only", id="inscope-checkbox")
                yield Button("Refresh", id="refresh-btn", variant="primary")

            # Status bar
            yield Static("Loading assets...", id="assets-status")

            # Main content
            with Horizontal(id="assets-content"):
                with Vertical(id="assets-table-container"):
                    yield AssetTable(id="asset-table")

                with Vertical(id="asset-detail-container"):
                    yield Static("[bold]Asset Details[/bold]", id="detail-header")
                    yield AssetDetail(id="asset-detail")

        # Footer with keyboard shortcuts
        yield Footer()

    async def on_mount(self) -> None:
        """Called when screen is mounted"""
        # Start periodic refresh (every 10 seconds)
        self._refresh_timer = self.set_interval(10.0, self.refresh_assets, pause=False)

        # Initial load
        await self.refresh_assets()

    async def on_unmount(self) -> None:
        """Called when screen is unmounted"""
        if self._refresh_timer:
            self._refresh_timer.stop()

    async def refresh_assets(self) -> None:
        """Fetch and display assets"""
        try:
            status = self.query_one("#assets-status", Static)
            status.update("[cyan]Loading assets...[/cyan]")

            # Build filters
            kwargs = {}
            if self.filter_text:
                # Assume filter is domain if it contains dots
                if "." in self.filter_text:
                    kwargs['domain'] = self.filter_text
            if self.in_scope_only:
                kwargs['in_scope_only'] = True

            # Fetch assets
            assets = await self.bbot_app.data_service.list_assets(**kwargs)

            # Update table
            table = self.query_one("#asset-table", AssetTable)
            table.update_assets(assets)

            # Update status
            if assets:
                status.update(f"[green]Loaded {len(assets)} assets[/green]")
            else:
                status.update("[yellow]No assets found[/yellow]")

        except Exception as e:
            status = self.query_one("#assets-status", Static)
            status.update(f"[red]Error loading assets: {e}[/red]")
            self.notify(f"Failed to load assets: {e}", severity="error", timeout=5)

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
        # Trigger refresh with new filter
        self.run_worker(self.refresh_assets())

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle checkbox changes"""
        if event.checkbox.id == "inscope-checkbox":
            self.in_scope_only = event.value
            # Trigger refresh
            self.run_worker(self.refresh_assets())

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "refresh-btn":
            await self.action_refresh()

    async def action_refresh(self) -> None:
        """Refresh assets"""
        await self.refresh_assets()
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

    def action_toggle_inscope(self) -> None:
        """Toggle in-scope only filter"""
        checkbox = self.query_one("#inscope-checkbox", Checkbox)
        checkbox.toggle()
