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
from bbot_server.cli.tui.widgets.paginated_table import PaginatedTableContainer


class EventsScreen(Container):
    """Events viewer screen with filtering"""

    filter_text = reactive("")

    def __init__(self, app):
        super().__init__()
        self.bbot_app = app
        self._refresh_timer = None
        self._has_loaded = False
        self._cached_events = []  # Cache all events to avoid refetching on page changes

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
                    yield PaginatedTableContainer(
                        EventTable(id="event-table"),
                        items_per_page=self.bbot_app.items_per_page,
                        id="event-pagination"
                    )

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
        await self.refresh_events(show_loading=True)

        # Resume periodic refresh
        if self._refresh_timer:
            self._refresh_timer.resume()

    async def on_unmount(self) -> None:
        """Called when screen is unmounted"""
        if self._refresh_timer:
            self._refresh_timer.stop()

    async def refresh_events(self, show_loading: bool = False) -> None:
        """Fetch and cache all events from server

        Args:
            show_loading: If True, show "Loading..." status message (for manual refreshes)
        """
        # Check if services are initialized
        if not self.bbot_app.data_service:
            return

        try:
            status = self.query_one("#events-status", Static)
            # Only show loading message on initial load or manual refresh
            if show_loading:
                status.update("[cyan]Loading events...[/cyan]")

            # Fetch ALL events and cache them (no skip/limit)
            self._cached_events = await self.bbot_app.data_service.list_events()

            # Update table from cache
            self._update_table_from_cache()

        except Exception as e:
            # Show error
            try:
                status = self.query_one("#events-status", Static)
                status.update(f"[red]Error loading events: {e}[/red]")
            except:
                pass

    def _update_table_from_cache(self) -> None:
        """Update table display from cached data (for page changes without refetching)"""
        try:
            # Apply client-side filter if any
            filtered_events = self._cached_events
            if self.filter_text:
                filter_lower = self.filter_text.lower()
                filtered_events = [
                    e for e in self._cached_events
                    if filter_lower in getattr(e, 'type', '').lower()
                    or filter_lower in getattr(e, 'host', '').lower()
                    or filter_lower in getattr(e, 'data', '').lower()
                ]

            # Get pagination container
            pagination = self.query_one("#event-pagination", PaginatedTableContainer)
            skip, limit = pagination.get_skip_limit()

            # Apply pagination to filtered results
            paginated_events = filtered_events[skip:skip + limit]

            # Update table with paginated subset
            table = self.query_one("#event-table", EventTable)
            table.update_events(paginated_events)

            # Update pagination total_items (using filtered count)
            pagination.total_items = len(filtered_events)

            # Update status
            status = self.query_one("#events-status", Static)
            if paginated_events:
                if self.filter_text:
                    status.update(f"[green]Showing {len(paginated_events)} of {len(filtered_events)} filtered events[/green]")
                else:
                    status.update(f"[green]Showing {len(paginated_events)} events[/green]")
            else:
                status.update("[yellow]No events found[/yellow]")

        except Exception:
            pass

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

    def on_paginated_table_container_page_changed(self, message: PaginatedTableContainer.PageChanged) -> None:
        """Handle page changes - update from cache without refetching"""
        self._update_table_from_cache()

    def on_filter_bar_filter_changed(self, event: FilterBar.FilterChanged) -> None:
        """Handle filter text changes"""
        self.filter_text = event.filter_text
        # Reset to first page when filter changes
        try:
            pagination = self.query_one("#event-pagination", PaginatedTableContainer)
            pagination.reset_to_first_page()
        except Exception:
            pass
        # Trigger refresh (show loading since user-initiated)
        self.run_worker(self.refresh_events(show_loading=True))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "refresh-btn":
            await self.action_refresh()

    async def action_refresh(self) -> None:
        """Refresh events"""
        await self.refresh_events(show_loading=True)
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
