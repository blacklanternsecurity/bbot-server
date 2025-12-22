"""
Technologies screen for BBOT Server TUI
"""
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, Button
from textual.reactive import reactive

from bbot_server.cli.tui.widgets.technology_table import TechnologyTable
from bbot_server.cli.tui.widgets.technology_detail import TechnologyDetail
from bbot_server.cli.tui.widgets.filter_bar import FilterBar


class TechnologiesScreen(Container):
    """Technologies viewer screen with filtering"""

    filter_text = reactive("")

    def __init__(self, app):
        super().__init__()
        self.bbot_app = app
        self._refresh_timer = None
        self._has_loaded = False

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        with Container(id="technologies-container"):
            # Filter controls
            with Horizontal(id="technology-controls"):
                yield FilterBar(placeholder="Search by technology name, host, or domain...", id="technology-filter")
                yield Button("Refresh", id="refresh-btn", variant="primary")

            # Status bar
            yield Static("Loading technologies...", id="technologies-status")

            # Main content
            with Horizontal(id="technologies-content"):
                with Vertical(id="technologies-table-container"):
                    yield TechnologyTable(id="technology-table")

                with Vertical(id="technology-detail-container"):
                    yield Static("[bold]Technology Details[/bold]", id="detail-header")
                    yield TechnologyDetail(id="technology-detail")

    async def on_mount(self) -> None:
        """Called when screen is mounted"""
        # Start periodic refresh (paused until first load)
        self._refresh_timer = self.set_interval(10.0, self.refresh_technologies, pause=True)

    async def load_initial_data(self) -> None:
        """Load data on first visit to this tab"""
        if self._has_loaded:
            return

        self._has_loaded = True
        await self.refresh_technologies()

        # Resume periodic refresh
        if self._refresh_timer:
            self._refresh_timer.resume()

    async def on_unmount(self) -> None:
        """Called when screen is unmounted"""
        if self._refresh_timer:
            self._refresh_timer.stop()

    async def refresh_technologies(self) -> None:
        """Fetch and display technologies"""
        # Check if services are initialized
        if not self.bbot_app.data_service:
            return

        try:
            status = self.query_one("#technologies-status", Static)
            status.update("[cyan]Loading technologies...[/cyan]")

            # Build filters based on filter text
            kwargs = {}
            if self.filter_text:
                # If it contains dots, assume it's a domain/host
                if "." in self.filter_text:
                    kwargs['domain'] = self.filter_text
                else:
                    # Otherwise search in technology names
                    kwargs['search'] = self.filter_text

            # Fetch technologies
            technologies = await self.bbot_app.data_service.list_technologies(**kwargs)

            # Update table
            table = self.query_one("#technology-table", TechnologyTable)
            table.update_technologies(technologies)

            # Update status
            if technologies:
                status.update(f"[green]Loaded {len(technologies)} technologies[/green]")
            else:
                status.update("[yellow]No technologies found[/yellow]")

        except Exception as e:
            try:
                status = self.query_one("#technologies-status", Static)
                status.update(f"[red]Error loading technologies: {e}[/red]")
            except:
                pass
            self.notify(f"Failed to load technologies: {e}", severity="error", timeout=5)

    def on_data_table_row_highlighted(self, event) -> None:
        """Handle row selection"""
        # Only handle events from the technology table
        if event.data_table.id != "technology-table":
            return

        table = self.query_one("#technology-table", TechnologyTable)
        selected_technology = table.get_selected_technology()

        # Update detail panel
        detail = self.query_one("#technology-detail", TechnologyDetail)
        detail.update_technology(selected_technology)

    def on_filter_bar_filter_changed(self, event: FilterBar.FilterChanged) -> None:
        """Handle filter text changes"""
        self.filter_text = event.filter_text
        # Trigger refresh
        self.run_worker(self.refresh_technologies())

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "refresh-btn":
            await self.action_refresh()

    async def action_refresh(self) -> None:
        """Refresh technologies"""
        await self.refresh_technologies()
        self.notify("Technologies refreshed", timeout=2)

    def action_focus_filter(self) -> None:
        """Focus the filter input"""
        filter_bar = self.query_one("#technology-filter", FilterBar)
        filter_bar.focus()

    def action_clear_filter(self) -> None:
        """Clear the filter"""
        filter_bar = self.query_one("#technology-filter", FilterBar)
        filter_bar.clear_filter()
        self.filter_text = ""
