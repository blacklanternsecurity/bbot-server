"""
Create Target modal for BBOT Server TUI
"""
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Static, Input, TextArea, Button, Checkbox


class CreateTargetModal(ModalScreen[dict | None]):
    """Modal dialog for creating a new target"""

    CSS = """
    CreateTargetModal {
        align: center middle;
    }

    #dialog {
        width: 80;
        height: auto;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }

    #title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: #FF8400;
        padding: 0 0 1 0;
    }

    .form-label {
        width: 100%;
        padding: 1 0 0 0;
        color: #FF8400;
    }

    Input {
        width: 100%;
        margin: 0 0 0 0;
    }

    TextArea {
        width: 100%;
        height: 5;
        margin: 0 0 0 0;
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

    def compose(self) -> ComposeResult:
        """Create the modal dialog"""
        with Container(id="dialog"):
            yield Static("Create New Target", id="title")

            yield Static("Name:", classes="form-label")
            yield Input(placeholder="Target name (leave empty for auto-generated)", id="name-input")

            yield Static("Description:", classes="form-label")
            yield Input(placeholder="Target description", id="description-input")

            yield Static("Target (one per line - domains, IPs, CIDRs, URLs):", classes="form-label")
            yield TextArea(id="target-input")

            yield Static("Seeds (one per line - leave empty to use target list):", classes="form-label")
            yield TextArea(id="seeds-input")

            yield Static("Blacklist (one per line):", classes="form-label")
            yield TextArea(id="blacklist-input")

            yield Checkbox("Strict DNS Scope", id="strict-scope-checkbox")

            with Horizontal(id="button-container"):
                yield Button("Create", id="create-btn", variant="primary")
                yield Button("Cancel", id="cancel-btn", variant="default")

    def on_mount(self) -> None:
        """Focus the name input when modal opens"""
        self.query_one("#name-input", Input).focus()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "cancel-btn":
            self.dismiss(None)
        elif event.button.id == "create-btn":
            await self.handle_create()

    async def handle_create(self) -> None:
        """Collect form data and dismiss with result"""
        # Get input values
        name = self.query_one("#name-input", Input).value.strip()
        description = self.query_one("#description-input", Input).value.strip()
        target_text = self.query_one("#target-input", TextArea).text.strip()
        seeds_text = self.query_one("#seeds-input", TextArea).text.strip()
        blacklist_text = self.query_one("#blacklist-input", TextArea).text.strip()
        strict_scope = self.query_one("#strict-scope-checkbox", Checkbox).value

        # Parse lists (split by newlines and filter empty)
        target_list = [line.strip() for line in target_text.split('\n') if line.strip()]
        seeds_list = [line.strip() for line in seeds_text.split('\n') if line.strip()] if seeds_text else None
        blacklist_list = [line.strip() for line in blacklist_text.split('\n') if line.strip()] if blacklist_text else None

        # Validate: must have at least target or seeds
        if not target_list and not seeds_list:
            self.app.notify("Must provide at least one target or seed", severity="error", timeout=3)
            return

        # Return the form data
        result = {
            "name": name if name else "",  # Empty name will trigger auto-generation
            "description": description,
            "target": target_list if target_list else None,
            "seeds": seeds_list,
            "blacklist": blacklist_list,
            "strict_dns_scope": strict_scope,
        }
        self.dismiss(result)
