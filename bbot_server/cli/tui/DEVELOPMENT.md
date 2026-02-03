# BBOT Server TUI - Developer Guide

Technical documentation for developers working on or extending the BBOT Server TUI.

## Architecture Overview

### Tech Stack
- **Framework**: Textual 0.85.0 (Python TUI framework)
- **Rendering**: Rich 13.9.4 (Terminal formatting)
- **Async**: Python 3.10+ asyncio
- **HTTP Client**: Existing BBOTServer client
- **WebSocket**: Built-in WebSocket support via BBOTServer

### Design Pattern: Service-Screen-Widget

```
BBOTServerTUI (App)
├── Services (Business Logic)
│   ├── DataService (HTTP API)
│   ├── WebSocketService (Real-time)
│   └── StateService (State Management)
├── Screens (Views)
│   ├── DashboardScreen
│   ├── ScansScreen
│   └── ... (6 total)
└── Widgets (Components)
    ├── ScanTable
    ├── ScanDetail
    └── ... (9 total)
```

### Directory Structure

```
bbot_server/cli/tui/
├── app.py                  # Main app, screen routing
├── tui_cli.py             # CLI integration
├── styles.tcss            # Textual CSS
├── screens/               # Screen implementations
│   └── *.py              # One file per screen
├── widgets/               # Reusable components
│   └── *.py              # One file per widget
├── services/              # Business logic
│   ├── data_service.py   # API wrapper
│   ├── websocket_service.py  # WebSocket handling
│   └── state_service.py  # State management
└── utils/                 # Helpers
    ├── formatters.py     # Data formatting
    ├── colors.py         # Color/style utils
    └── keybindings.py    # Keyboard shortcuts
```

## Core Components

### 1. Application (app.py)

**BBOTServerTUI Class**

Main application class that handles:
- Screen installation and routing
- Service initialization
- Global keyboard bindings
- App lifecycle

```python
class BBOTServerTUI(App):
    TITLE = "BBOT Server"
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("d", "show_dashboard", "Dashboard"),
        # ... more bindings
    ]

    def __init__(self, bbot_server, config):
        self.bbot_server = bbot_server  # HTTP client
        self.config = config
        # Services initialized in on_mount()
```

**Key Methods:**
- `on_mount()` - Initialize services, install screens
- `action_show_*()` - Screen navigation handlers
- `push_screen(name)` - Switch to a screen

### 2. CLI Integration (tui_cli.py)

**TUICTL Class**

Integrates with existing bbctl CLI:

```python
class TUICTL(BaseBBCTL):
    command = "tui"
    attach_to = "bbctl"  # Auto-registers with bbctl

    def main(self):
        app = BBOTServerTUI(
            bbot_server=self.bbot_server,  # From parent
            config=self.config
        )
        app.run()
```

**Auto-Discovery:**
- File ends with `_cli.py` → Auto-discovered
- Inherits `BaseBBCTL` → Recognized as CLI module
- Sets `attach_to = "bbctl"` → Registered as subcommand

### 3. Services Layer

#### DataService (services/data_service.py)

HTTP API wrapper with error handling:

```python
class DataService:
    def __init__(self, bbot_server):
        self.bbot_server = bbot_server

    async def get_scans(self) -> List[Any]:
        try:
            scans = list(self.bbot_server.get_scans())
            return scans
        except BBOTServerError as e:
            log.error(f"Error: {e}")
            return []
```

**Methods (20+):**
- Scans: get_scans, get_scan, start_scan, cancel_scan
- Assets: list_assets, get_asset
- Findings: list_findings
- Activities: list_activities
- Agents: get_agents, create_agent, delete_agent
- Stats: get_stats
- Config: get_targets, get_presets

#### WebSocketService (services/websocket_service.py)

Real-time streaming with auto-reconnection:

```python
class WebSocketService:
    async def tail_activities(self, n=10):
        """Generator that yields activities from WebSocket"""
        async for activity in self.bbot_server.tail_activities(n=n):
            yield activity

    async def _stream_with_reconnect(self):
        """Background task with exponential backoff"""
        backoff = 1
        while self._is_streaming:
            try:
                async for activity in self.tail_activities():
                    # Process activity
                    backoff = 1  # Reset on success
            except Exception:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
```

**Features:**
- Exponential backoff (1s → 60s)
- Callback pattern for subscribers
- Auto-reconnection on disconnect
- Background task management

#### StateService (services/state_service.py)

Shared application state:

```python
class StateService:
    def __init__(self):
        self.scans = {}
        self.assets = {}
        # ... more state

    def update_scan(self, scan):
        """Update or add scan to state"""
        self.scans[scan.id] = scan
```

**Purpose:**
- Cache data across screens
- Synchronize updates from WebSocket
- Resolve update conflicts

### 4. Screens

#### Base Screen Pattern

All screens follow this pattern:

```python
class ExampleScreen(Screen):
    """Screen description"""

    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        # ... more bindings
    ]

    # Reactive state
    filter_text = reactive("")

    def __init__(self, app):
        super().__init__()
        self.bbot_app = app
        self._refresh_timer = None

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        with Container():
            yield FilterBar()
            yield DataTable()

    async def on_mount(self) -> None:
        """Start timers, load data"""
        self._refresh_timer = self.set_interval(5.0, self.refresh)
        await self.refresh()

    async def on_unmount(self) -> None:
        """Cleanup"""
        if self._refresh_timer:
            self._refresh_timer.stop()

    async def refresh(self) -> None:
        """Fetch and display data"""
        data = await self.bbot_app.data_service.get_data()
        # Update widgets
```

#### Screen Lifecycle

1. **Mount** (`on_mount`)
   - Initialize widgets
   - Start timers
   - Load initial data

2. **Active** (event handling)
   - Handle user input
   - Process events
   - Update reactive state

3. **Unmount** (`on_unmount`)
   - Stop timers
   - Cancel workers
   - Cleanup resources

### 5. Widgets

#### Base Widget Pattern

```python
class ExampleWidget(DataTable):
    """Widget description"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._data = []

    def on_mount(self) -> None:
        """Setup widget"""
        self.add_columns("Col1", "Col2")

    def update_data(self, data: List) -> None:
        """Update widget with new data"""
        self.clear()
        for item in data:
            self.add_row(item.field1, item.field2)
```

#### Widget Types

**Tables:**
- `ScanTable` - Scan list with sorting
- `AssetTable` - Asset list with filtering
- `FindingTable` - Finding list with severity colors

**Detail Panels:**
- `ScanDetail` - Scan information display
- `AssetDetail` - Asset information display
- `FindingDetail` - Finding information display

**Interactive:**
- `FilterBar` - Search input with events
- `ActivityFeed` - Auto-scrolling log

### 6. Utilities

#### Formatters (utils/formatters.py)

Data formatting functions:

```python
def format_timestamp_short(timestamp: float) -> str:
    """Format timestamp for tables (12:34, Jan 01)"""

def format_duration_short(seconds: float) -> str:
    """Format duration compactly (2d 5h, 5m 23s)"""

def format_list(items: List[str], max_items: int = 3) -> str:
    """Format list with truncation (item1, item2 (+3 more))"""
```

**15+ Functions:**
- Timestamps: short, long, human-readable
- Durations: short, long
- Lists: truncated with "more" indicator
- Numbers: comma separators
- Strings: truncation, host formatting

#### Colors (utils/colors.py)

Color and style utilities:

```python
# Severity score to color
SEVERITY_COLORS_TEXTUAL = {
    1: "blue",      # INFO
    2: "yellow",    # LOW
    3: "bright_magenta",  # MEDIUM
    4: "red",       # HIGH
    5: "magenta",   # CRITICAL
}

def get_severity_color(severity_score: int) -> str:
    """Get Textual color for severity"""

def colorize_severity(severity_name: str, text: str) -> str:
    """Wrap text in Rich markup with color"""
```

**Features:**
- Multiple format support (Textual, CSS, Rich)
- Severity color mappings (1-5)
- Status color mappings (RUNNING, DONE, etc.)
- Helper functions for colorization

#### Keybindings (utils/keybindings.py)

Centralized keyboard shortcuts:

```python
GLOBAL_BINDINGS = [
    KeyBinding("q", "quit", "Quit"),
    KeyBinding("d", "show_dashboard", "Dashboard"),
    # ... more
]

SCAN_BINDINGS = [
    KeyBinding("n", "new_scan", "New Scan"),
    # ... more
]
```

**Functions:**
- `get_bindings_for_screen(name)` - Get screen bindings
- `format_key_hint(bindings)` - Format for status bar
- `get_help_text(screen_name)` - Generate help text

## Data Flow

### HTTP Request Flow

```
User Action (key press, button click)
    ↓
Action Handler (action_* method)
    ↓
DataService Method (async)
    ↓
BBOTServer HTTP Client
    ↓
BBOT Server API
    ↓
Response (Pydantic models)
    ↓
Update Widget
    ↓
Textual Render
```

### WebSocket Flow

```
Screen Mount
    ↓
Start WebSocketService
    ↓
Create Worker (@work decorator)
    ↓
Stream Activities (async for)
    ↓
For Each Activity:
    ↓
    Post Message to Main Thread
    ↓
    Message Handler (on_*)
    ↓
    Update Widget
    ↓
    Textual Render
```

### Reactive State Flow

```
User Input (filter text)
    ↓
Update Reactive Variable
    ↓
Trigger Watch Method (watch_*)
    ↓
Process Change
    ↓
Update UI
```

Example:
```python
filter_text = reactive("")  # Reactive variable

def watch_filter_text(self, old, new):
    """Called when filter_text changes"""
    self.apply_filter(new)
```

## Common Patterns

### 1. Periodic Refresh

```python
async def on_mount(self):
    # Refresh every 5 seconds
    self._refresh_timer = self.set_interval(
        5.0,           # Interval in seconds
        self.refresh,  # Method to call
        pause=False    # Start immediately
    )

async def on_unmount(self):
    # Stop timer on cleanup
    if self._refresh_timer:
        self._refresh_timer.stop()
```

### 2. Background Worker

```python
@work(exclusive=True)
async def stream_data(self):
    """Run in background"""
    try:
        async for item in self.data_stream():
            # Process item
            self.post_message(ItemReceived(item))
    except Exception as e:
        log.error(f"Stream error: {e}")

def on_mount(self):
    # Start worker
    self._worker = self.run_worker(self.stream_data())

def on_unmount(self):
    # Cancel worker
    if self._worker:
        self._worker.cancel()
```

### 3. Error Handling

```python
async def fetch_data(self):
    try:
        data = await self.service.get_data()
        # Update UI with data
        self.show_success()
    except BBOTServerUnauthorizedError:
        self.notify("Auth failed", severity="error")
    except BBOTServerNotFoundError:
        self.notify("Not found", severity="warning")
    except BBOTServerError as e:
        self.notify(f"Error: {e}", severity="error")
        log.error(f"Fetch failed: {e}")
```

### 4. Message Passing

```python
# Define custom message
class DataReceived(Message):
    def __init__(self, data):
        super().__init__()
        self.data = data

# Send message
self.post_message(DataReceived(my_data))

# Handle message
def on_data_received(self, message: DataReceived):
    """Handle custom message"""
    self.process_data(message.data)
```

### 5. Widget Query

```python
# Query by ID
table = self.query_one("#scan-table", ScanTable)

# Query by type
all_buttons = self.query(Button)

# Update widget
table.update_scans(scans)
```

## Styling with TCSS

### Basic Selectors

```css
/* By widget type */
Button {
    background: #FF8400;
}

/* By ID */
#scan-table {
    border: solid white;
}

/* By class */
.stat-card {
    height: 7;
    border: solid #FF8400;
}

/* Pseudo-classes */
Button:hover {
    background: #FF8400 80%;
}

DataTable:focus {
    border: solid #FF8400;
}
```

### Layout Properties

```css
/* Sizing */
Container {
    height: 100%;
    width: 100%;
}

/* Flexbox-like */
Horizontal {
    height: auto;  /* Fit content */
}

Vertical {
    width: 1fr;    /* Fill space */
}

/* Grid */
#stats-grid {
    grid-size: 5 1;     /* 5 columns, 1 row */
    grid-gutter: 1;     /* Spacing */
}

/* Spacing */
Button {
    margin: 0 1;   /* Vertical 0, Horizontal 1 */
    padding: 1;
}
```

### Color & Text

```css
.severity-critical {
    background: purple;
    color: white;
    text-style: bold;
}

Static {
    text-align: center;
    color: #FF8400;
}
```

## Testing

### Manual Testing

```bash
# Start server
bbctl server start

# Launch TUI
bbctl tui

# Test each screen
# Press d, s, a, f, v, g

# Test interactions
# Filter, refresh, select items
```

### Integration Testing (Future)

```python
from textual.pilot import Pilot

async def test_scans_screen():
    app = BBOTServerTUI(mock_client, mock_config)
    async with app.run_test() as pilot:
        # Navigate to scans
        await pilot.press("s")
        assert app.screen.name == "scans"

        # Verify table populated
        table = app.query_one("#scan-table")
        assert table.row_count > 0
```

### Unit Testing

```python
def test_format_duration_short():
    assert format_duration_short(3665) == "1h 1m"
    assert format_duration_short(45) == "45s"

def test_severity_color():
    assert get_severity_color(5) == "magenta"  # CRITICAL
    assert get_severity_color(1) == "blue"     # INFO
```

## Debugging

### Enable Debug Logging

```bash
# Launch with debug
bbctl --debug tui

# View logs
tail -f ~/.config/bbot_server/logs/bbot-server.log
```

### Add Logging

```python
import logging
log = logging.getLogger(__name__)

# In methods
log.debug(f"Fetching {count} items")
log.info(f"User action: {action}")
log.warning(f"Retry attempt {attempt}")
log.error(f"Failed: {error}")
```

### Textual Dev Tools

```bash
# Launch with devtools
textual run --dev bbctl tui

# Console will show:
# - Widget tree
# - CSS inspector
# - Message log
# - Performance stats
```

### Print Debugging

```python
# In Textual, use app.bell() for notifications
self.app.bell()  # Makes terminal beep

# Or use notify
self.notify(f"Debug: {value}")

# Or write to log
self.log(f"Debug info: {data}")
```

## Performance Optimization

### 1. Efficient Table Updates

```python
# Good: Clear and rebuild
table.clear()
for item in items:
    table.add_row(...)

# Bad: Remove rows one by one
for row_key in table.rows:
    table.remove_row(row_key)
```

### 2. Limit Data Size

```python
# Limit results from API
async def list_assets(self, limit=1000):
    assets = await self.service.list_assets()
    return assets[:limit]  # Cap at 1000

# Buffer activity feed
class ActivityFeed:
    def __init__(self, max_activities=1000):
        self._activities = deque(maxlen=1000)
```

### 3. Debounce Filters

```python
# Use reactive with debounce (future)
filter_text = reactive("", init=False)

def watch_filter_text(self, value):
    # Only trigger after typing stops
    self.set_timer(0.5, lambda: self.apply_filter(value))
```

### 4. Cancel Workers

```python
def on_unmount(self):
    # Always cancel workers
    if self._worker:
        self._worker.cancel()

    # Stop timers
    if self._timer:
        self._timer.stop()
```

## Adding Features

### Add a New Screen

1. **Create screen file:**
```python
# screens/my_screen.py
from textual.screen import Screen

class MyScreen(Screen):
    def __init__(self, app):
        super().__init__()
        self.bbot_app = app
```

2. **Add to app.py:**
```python
# Import
from bbot_server.cli.tui.screens.my_screen import MyScreen

# In on_mount()
self.install_screen(MyScreen(self), name="my_screen")

# Add action
def action_show_my_screen(self):
    self.push_screen("my_screen")

# Add binding
BINDINGS = [
    Binding("m", "show_my_screen", "My Screen"),
]
```

### Add a Widget

1. **Create widget file:**
```python
# widgets/my_widget.py
from textual.widgets import Static

class MyWidget(Static):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._data = []

    def update_data(self, data):
        self._data = data
        self.update(str(data))
```

2. **Use in screen:**
```python
from bbot_server.cli.tui.widgets.my_widget import MyWidget

def compose(self):
    yield MyWidget(id="my-widget")

def update_display(self):
    widget = self.query_one("#my-widget", MyWidget)
    widget.update_data(self.data)
```

### Add API Method

1. **Add to DataService:**
```python
async def get_my_data(self, filters=None):
    try:
        data = list(self.bbot_server.get_my_data(**filters))
        return data
    except BBOTServerError as e:
        log.error(f"Error: {e}")
        return []
```

2. **Use in screen:**
```python
async def refresh(self):
    data = await self.bbot_app.data_service.get_my_data()
    self.update_display(data)
```

### Add Keyboard Shortcut

1. **Define in screen:**
```python
BINDINGS = [
    Binding("x", "my_action", "My Action"),
]
```

2. **Add action handler:**
```python
def action_my_action(self):
    """Handle x key"""
    self.notify("Action executed!")
```

3. **Add to keybindings.py (optional):**
```python
MY_SCREEN_BINDINGS = [
    KeyBinding("x", "my_action", "My Action"),
]
```

## Best Practices

### 1. Error Handling

- ✅ Always use try/except for API calls
- ✅ Provide user-friendly error messages
- ✅ Log errors for debugging
- ✅ Graceful degradation (show cached data)

### 2. Resource Management

- ✅ Stop timers in on_unmount()
- ✅ Cancel workers in on_unmount()
- ✅ Close connections properly
- ✅ Limit buffer sizes

### 3. User Experience

- ✅ Show loading indicators
- ✅ Provide feedback for actions
- ✅ Use notifications sparingly
- ✅ Keep UI responsive

### 4. Code Quality

- ✅ Type hints on all methods
- ✅ Docstrings for public methods
- ✅ Consistent naming conventions
- ✅ Follow DRY principle

### 5. Performance

- ✅ Limit API result sizes
- ✅ Use efficient data structures
- ✅ Debounce expensive operations
- ✅ Profile with Textual devtools

## Common Issues

### Issue: Widget Not Updating

**Problem:** Changed data but widget doesn't update

**Solution:** Call update method explicitly
```python
# After changing data
widget.update_data(new_data)
# or
self.refresh()
```

### Issue: Memory Leak

**Problem:** Memory grows over time

**Solution:** Limit buffer sizes
```python
self._items = deque(maxlen=1000)  # Auto-truncates
```

### Issue: WebSocket Stops

**Problem:** Activity feed freezes

**Solution:** Implement auto-reconnect
```python
# Already implemented in WebSocketService
# Check server logs for connection issues
```

### Issue: Layout Broken

**Problem:** Widgets overlap or disappear

**Solution:** Check TCSS styling
```css
/* Ensure proper sizing */
Container {
    height: 100%;
}

DataTable {
    height: 1fr;  /* Fill remaining space */
}
```

## Contributing

### Code Style

- Follow PEP 8
- Use type hints
- Write docstrings (Google style)
- Keep methods short (<50 lines)
- Use meaningful variable names

### Commit Messages

```
feat: Add new widget for X
fix: Correct table sorting bug
docs: Update developer guide
refactor: Simplify data service
test: Add tests for formatters
```

### Pull Request Process

1. Fork repository
2. Create feature branch
3. Make changes
4. Test thoroughly
5. Update documentation
6. Submit PR with description

## Resources

- **Textual Docs**: https://textual.textualize.io/
- **Rich Markup**: https://rich.readthedocs.io/en/stable/markup.html
- **BBOT API**: http://localhost:8807/v1/docs
- **Python Async**: https://docs.python.org/3/library/asyncio.html

## Support

For questions or issues:
- Check CLAUDE.md for architecture
- Read README.md for user guide
- Review existing code examples
- Open GitHub issue if stuck
