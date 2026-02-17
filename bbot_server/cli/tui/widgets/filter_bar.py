"""
Filter bar widget for BBOT Server TUI
"""

from textual.widgets import Input
from textual.message import Message


class FilterBar(Input):
    """
    Input widget for filtering table data

    Provides a search/filter input with custom styling and
    filter change events.
    """

    class FilterChanged(Message):
        """Message sent when filter text changes"""

        def __init__(self, filter_text: str):
            super().__init__()
            self.filter_text = filter_text

    def __init__(self, placeholder: str = "Filter...", **kwargs):
        super().__init__(placeholder=placeholder, **kwargs)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes and post filter change message"""
        self.post_message(self.FilterChanged(event.value))

    def clear_filter(self) -> None:
        """Clear the filter input"""
        self.value = ""
