"""
Events screen for BBOT Server TUI
"""
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, Button
from textual.reactive import reactive

from bbot_server.cli.tui.widgets.event_table import EventTable
from bbot_server.cli.tui.widgets.event_detail import EventDetail
from bbot_server.cli.tui.widgets.filter_bar import FilterBar


class EventsScreen(Container):
    """Events viewer screen with filtering"""

    filter_text = reactive("")

    def __init__(self, app):
        super().__init__()
        self.bbot_app = app
        self._refresh_timer = None
        self._has_loaded = False

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        with Container(id="events-container"):
            # Filter controls
            with Horizontal(id="event-controls"):
                yield FilterBar(placeholder="Filter by type, host, or domain...", id="event-filter")
                yield Button("Refresh", id="refresh-btn", variant="primary")

            # Status bar
            yield Static("Loading events...", id="events-status")

            # Main content
            with Horizontal(id="events-content"):
                with Vertical(id="events-table-container"):
                    yield EventTable(id="event-table")

                with Vertical(id="event-detail-container"):
                    yield Static("[bold]Event Details[/bold]", id="detail-header")
                    yield EventDetail(id="event-detail")

    async def on_mount(self) -> None:
        """Called when screen is mounted"""
        # Start periodic refresh (paused until first load)
        self._refresh_timer = self.set_interval(10.0, self.refresh_events, pause=True)

    async def load_initial_data(self) -> None:
        """Load data on first visit to this tab"""
        if self._has_loaded:
            return

        self._has_loaded = True
        await self.refresh_events()

        # Resume periodic refresh
        if self._refresh_timer:
            self._refresh_timer.resume()

    async def on_unmount(self) -> None:
        """Called when screen is unmounted"""
        if self._refresh_timer:
            self._refresh_timer.stop()

    async def refresh_events(self) -> None:
        """Fetch and display events"""
        # Check if services are initialized
        if not self.bbot_app.data_service:
            return

        try:
            status = self.query_one("#events-status", Static)
            status.update("[cyan]Loading events...[/cyan]")

            # Build filters based on filter text
            kwargs = {}
            if self.filter_text:
                # Try to determine what type of filter this is
                filter_lower = self.filter_text.lower()

                # If it contains dots, assume it's a domain/host
                if "." in self.filter_text:
                    # Could be domain or host - try both approaches
                    # For now, use domain filter which includes subdomains
                    kwargs['domain'] = self.filter_text
                else:
                    # Assume it's an event type
                    kwargs['event_type'] = self.filter_text

            # Fetch events
            events = await self.bbot_app.data_service.list_events(**kwargs)

            # Update table
            table = self.query_one("#event-table", EventTable)
            table.update_events(events)

            # Update status
            if events:
                status.update(f"[green]Loaded {len(events)} events[/green]")
            else:
                status.update("[yellow]No events found[/yellow]")

        except Exception as e:
            try:
                status = self.query_one("#events-status", Static)
                status.update(f"[red]Error loading events: {e}[/red]")
            except:
                pass
            self.notify(f"Failed to load events: {e}", severity="error", timeout=5)

    def on_data_table_row_highlighted(self, event) -> None:
        """Handle row selection"""
        # Only handle events from the event table
        if event.data_table.id != "event-table":
            return

        table = self.query_one("#event-table", EventTable)
        selected_event = table.get_selected_event()

        # Update detail panel
        detail = self.query_one("#event-detail", EventDetail)
        detail.update_event(selected_event)

    def on_filter_bar_filter_changed(self, event: FilterBar.FilterChanged) -> None:
        """Handle filter text changes"""
        self.filter_text = event.filter_text
        # Trigger refresh
        self.run_worker(self.refresh_events())

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "refresh-btn":
            await self.action_refresh()

    async def action_refresh(self) -> None:
        """Refresh events"""
        await self.refresh_events()
        self.notify("Events refreshed", timeout=2)

    def action_focus_filter(self) -> None:
        """Focus the filter input"""
        filter_bar = self.query_one("#event-filter", FilterBar)
        filter_bar.focus()

    def action_clear_filter(self) -> None:
        """Clear the filter"""
        filter_bar = self.query_one("#event-filter", FilterBar)
        filter_bar.clear_filter()
        self.filter_text = ""
