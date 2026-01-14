"""
Paginated table container widget for BBOT Server TUI

Provides pagination controls for any DataTable widget.
"""
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Static, Button
from textual.reactive import reactive
from textual.message import Message


class PaginatedTableContainer(Container):
    """
    Container that wraps a DataTable with pagination controls

    Adds Previous/Next buttons and page indicator below the table.
    Manages page state and exposes methods for data fetching.
    """

    current_page = reactive(1)
    total_pages = reactive(1)
    items_per_page = reactive(25)
    total_items = reactive(0)

    def __init__(self, table_widget, items_per_page=25, **kwargs):
        """
        Initialize paginated table container

        Args:
            table_widget: The DataTable widget to wrap
            items_per_page: Number of items to show per page (default: 25)
        """
        super().__init__(**kwargs)
        self.table = table_widget
        self.items_per_page = items_per_page
        self._status_id = f"{self.id}-pagination-status" if self.id else "pagination-status"
        self._prev_btn_id = f"{self.id}-prev-btn" if self.id else "prev-btn"
        self._next_btn_id = f"{self.id}-next-btn" if self.id else "next-btn"

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        yield self.table

        with Horizontal(classes="pagination-controls"):
            yield Button("◀ Previous", id=self._prev_btn_id, variant="default", disabled=True)
            yield Static(self._format_status(), id=self._status_id, classes="pagination-status")
            yield Button("Next ▶", id=self._next_btn_id, variant="default")

    def _format_status(self) -> str:
        """Format the pagination status text"""
        if self.total_items == 0:
            return "No items"

        start_item = (self.current_page - 1) * self.items_per_page + 1
        end_item = min(self.current_page * self.items_per_page, self.total_items)

        return f"Page {self.current_page} of {self.total_pages} ({start_item}-{end_item} of {self.total_items} items)"

    def _update_buttons(self) -> None:
        """Update button states based on current page"""
        try:
            prev_btn = self.query_one(f"#{self._prev_btn_id}", Button)
            next_btn = self.query_one(f"#{self._next_btn_id}", Button)

            prev_btn.disabled = self.current_page <= 1
            next_btn.disabled = self.current_page >= self.total_pages
        except Exception:
            pass

    def _update_status_text(self) -> None:
        """Update the status text"""
        try:
            status = self.query_one(f"#{self._status_id}", Static)
            status.update(self._format_status())
        except Exception:
            pass

    def watch_current_page(self, old_value: int, new_value: int) -> None:
        """React to page changes"""
        self._update_buttons()
        self._update_status_text()

    def watch_total_items(self, old_value: int, new_value: int) -> None:
        """React to total items changes"""
        # Recalculate total pages
        self.total_pages = max(1, (new_value + self.items_per_page - 1) // self.items_per_page)

        # Clamp current page if needed
        if self.current_page > self.total_pages:
            self.current_page = self.total_pages

        self._update_buttons()
        self._update_status_text()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle pagination button clicks"""
        if event.button.id == self._prev_btn_id:
            self.action_previous_page()
        elif event.button.id == self._next_btn_id:
            self.action_next_page()

    def action_previous_page(self) -> None:
        """Go to previous page"""
        if self.current_page > 1:
            self.current_page -= 1
            self.post_message(self.PageChanged(self.current_page))

    def action_next_page(self) -> None:
        """Go to next page"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.post_message(self.PageChanged(self.current_page))

    def reset_to_first_page(self) -> None:
        """Reset pagination to first page"""
        self.current_page = 1

    def get_skip_limit(self) -> tuple[int, int]:
        """
        Get skip and limit values for API calls

        Returns:
            Tuple of (skip, limit) for the current page
        """
        skip = (self.current_page - 1) * self.items_per_page
        limit = self.items_per_page
        return skip, limit

    class PageChanged(Message):
        """Message sent when page changes"""

        def __init__(self, page: int):
            super().__init__()
            self.page = page
