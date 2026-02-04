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
from bbot_server.cli.tui.utils.colors import loading_text, success_text, warning_text, error_text


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
            with Horizontal(id="event-controls", classes="controls-bar"):
                yield FilterBar(placeholder="Filter by type, host, or domain...", id="event-filter")
                yield Button("Refresh", id="refresh-btn", variant="primary")

            # Status bar
            yield Static("Loading events...", id="events-status", classes="status-bar")

            # Main content
            with Horizontal(id="events-content", classes="content-area"):
                with Vertical(id="events-table-container", classes="table-container"):
                    yield PaginatedTableContainer(
                        EventTable(id="event-table"), auto_page_size=True, id="event-pagination"
                    )

                with Vertical(id="event-detail-container", classes="detail-container"):
                    yield Static("[bold]Event Details[/bold]", id="detail-header")
                    yield EventDetail(id="event-detail", classes="detail-panel")

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
        """Fetch and display events from server with pagination

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
                status.update(loading_text("Loading events..."))

            # Get pagination parameters
            pagination = self.query_one("#event-pagination", PaginatedTableContainer)
            skip, limit = pagination.get_skip_limit()

            # Fetch events with server-side pagination and search
            search_term = self.filter_text if self.filter_text else None
            events, total = await self.bbot_app.data_service.get_events_paginated(
                skip=skip, limit=limit, search=search_term
            )

            # Update pagination with total count
            pagination.total_items = total

            # Update table with current page of events
            table = self.query_one("#event-table", EventTable)
            table.update_events(events)

            # Update status (pagination widget shows page info, status shows filter info)
            if total > 0:
                if self.filter_text:
                    status.update(success_text(f"Filtered: {total} events match"))
                else:
                    status.update(success_text(f"{total} total events"))
            else:
                status.update(warning_text("No events found"))

        except Exception as e:
            # Show error
            status = self.query_one("#events-status", Static)
            status.update(error_text(f"Error loading events: {e}"))

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
        # Reset to first page when filter changes
        pagination = self.query_one("#event-pagination", PaginatedTableContainer)
        pagination.reset_to_first_page()
        # Trigger refresh (show loading since user-initiated)
        self.run_worker(self.refresh_events(show_loading=True))

    def on_paginated_table_container_page_changed(self, event: PaginatedTableContainer.PageChanged) -> None:
        """Handle page navigation"""
        self.run_worker(self.refresh_events())

    def on_paginated_table_container_page_size_changed(self, event: PaginatedTableContainer.PageSizeChanged) -> None:
        """Handle page size changes from auto-sizing"""
        # Refetch data with new page size
        self.run_worker(self.refresh_events())

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
        # Reset pagination when filter is cleared
        pagination = self.query_one("#event-pagination", PaginatedTableContainer)
        pagination.reset_to_first_page()
