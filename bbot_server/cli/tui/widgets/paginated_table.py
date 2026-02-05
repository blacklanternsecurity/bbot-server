"""
Paginated table container widget for BBOT Server TUI

Provides pagination controls for any DataTable widget.
"""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Static, Button
from textual.reactive import reactive
from textual.message import Message
from textual.events import Resize


class PaginatedTableContainer(Container):
    """
    Container that wraps a DataTable with pagination controls

    Adds Previous/Next buttons and page indicator below the table.
    Manages page state and exposes methods for data fetching.

    If auto_page_size=True, automatically calculates items_per_page based
    on the available height of the container.
    """

    current_page = reactive(1)
    total_pages = reactive(1)
    items_per_page = reactive(0)  # 0 = not yet calculated
    total_items = reactive(0)

    # Height constants for auto-sizing
    PAGINATION_CONTROLS_HEIGHT = 3  # Height of prev/next buttons row
    TABLE_HEADER_HEIGHT = 1  # Height of DataTable header
    SCROLLBAR_HEIGHT = 1  # Height of horizontal scrollbar
    MIN_PAGE_SIZE = 5  # Minimum rows to show

    def __init__(self, table_widget, items_per_page=25, auto_page_size=False, **kwargs):
        """
        Initialize paginated table container

        Args:
            table_widget: The DataTable widget to wrap
            items_per_page: Number of items to show per page (default: 25, ignored if auto_page_size=True)
            auto_page_size: If True, automatically calculate page size based on available height
        """
        super().__init__(**kwargs)
        self.table = table_widget
        self._auto_page_size = auto_page_size
        self._initial_items_per_page = items_per_page
        if not auto_page_size:
            self.items_per_page = items_per_page
        self._status_id = f"{self.id}-pagination-status" if self.id else "pagination-status"
        self._prev_btn_id = f"{self.id}-prev-btn" if self.id else "prev-btn"
        self._next_btn_id = f"{self.id}-next-btn" if self.id else "next-btn"
        self._last_calculated_page_size = 0

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        yield self.table

        with Horizontal(classes="pagination-controls"):
            yield Button("◀ Previous", id=self._prev_btn_id, variant="default", disabled=True)
            yield Static(self._format_status(), id=self._status_id, classes="pagination-status")
            yield Button("Next ▶", id=self._next_btn_id, variant="default")

    def _format_status(self) -> str:
        """Format the pagination status text"""
        if self.total_items == 0 or self.items_per_page == 0:
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
        # Don't recalculate if page size not yet set
        if self.items_per_page == 0:
            return

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

    def get_skip_limit(self) -> tuple[int, int] | None:
        """
        Get skip and limit values for API calls

        Returns:
            Tuple of (skip, limit) for the current page, or None if page size not yet calculated
        """
        if self.items_per_page == 0:
            return None

        skip = (self.current_page - 1) * self.items_per_page
        limit = self.items_per_page
        return skip, limit

    class PageChanged(Message):
        """Message sent when page changes"""

        def __init__(self, page: int):
            super().__init__()
            self.page = page

    class PageSizeChanged(Message):
        """Message sent when page size changes (including initial calculation)"""

        def __init__(self, new_size: int, old_size: int):
            super().__init__()
            self.new_size = new_size
            self.old_size = old_size

    def on_mount(self) -> None:
        """Calculate initial page size when mounted"""
        if self._auto_page_size:
            self._calculate_page_size(self.size.height)

    def on_resize(self, event: Resize) -> None:
        """Recalculate page size when container is resized"""
        if self._auto_page_size:
            self._calculate_page_size(event.size.height)

    def _calculate_page_size(self, height: int) -> None:
        """Calculate items_per_page based on available height"""
        if height <= 0:
            return

        # Calculate available rows for data
        # Total height - pagination controls - table header - scrollbar
        available_rows = height - self.PAGINATION_CONTROLS_HEIGHT - self.TABLE_HEADER_HEIGHT - self.SCROLLBAR_HEIGHT

        # Ensure minimum page size
        new_page_size = max(self.MIN_PAGE_SIZE, available_rows)

        # Only update if changed significantly (avoid constant updates)
        if new_page_size != self._last_calculated_page_size:
            old_size = self.items_per_page

            self._last_calculated_page_size = new_page_size
            self.items_per_page = new_page_size

            # Recalculate total pages with new page size
            if self.total_items > 0:
                self.total_pages = max(1, (self.total_items + self.items_per_page - 1) // self.items_per_page)
                # Clamp current page if needed
                if self.current_page > self.total_pages:
                    self.current_page = self.total_pages

            # Emit PageSizeChanged whenever page size changes (including first calculation: 0 -> X)
            if old_size != new_page_size:
                self.post_message(self.PageSizeChanged(new_page_size, old_size))
