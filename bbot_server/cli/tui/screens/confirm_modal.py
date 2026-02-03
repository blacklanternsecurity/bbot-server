"""
Confirmation modal for BBOT Server TUI
"""
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Container, Horizontal
from textual.widgets import Static, Button


class ConfirmModal(ModalScreen[bool]):
    """Simple confirmation modal dialog"""

    CSS = """
    ConfirmModal {
        align: center middle;
    }

    #dialog {
        width: 60;
        height: auto;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }

    #title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: $primary;
        padding: 0 0 1 0;
    }

    #message {
        width: 100%;
        padding: 1 0;
    }

    #button-container {
        width: 100%;
        height: auto;
        align: center middle;
        padding: 1 0 0 0;
    }

    Button {
        margin: 0 1;
    }
    """

    def __init__(self, title: str, message: str, confirm_label: str = "Confirm", danger: bool = False) -> None:
        """Initialize the confirmation modal

        Args:
            title: Modal title
            message: Confirmation message
            confirm_label: Label for the confirm button
            danger: If True, confirm button is red (error variant)
        """
        super().__init__()
        self.title_text = title
        self.message = message
        self.confirm_label = confirm_label
        self.danger = danger

    def compose(self) -> ComposeResult:
        """Create the modal dialog"""
        with Container(id="dialog"):
            yield Static(self.title_text, id="title")
            yield Static(self.message, id="message")

            with Horizontal(id="button-container"):
                variant = "error" if self.danger else "primary"
                yield Button(self.confirm_label, id="confirm-btn", variant=variant)
                yield Button("Cancel", id="cancel-btn", variant="default")

    def on_mount(self) -> None:
        """Focus the cancel button by default for safety"""
        self.query_one("#cancel-btn", Button).focus()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "cancel-btn":
            self.dismiss(False)
        elif event.button.id == "confirm-btn":
            self.dismiss(True)
