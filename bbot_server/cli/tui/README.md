# BBOT Server TUI - User Guide

A comprehensive Terminal User Interface for managing BBOT security scans with real-time updates and interactive filtering.

## Quick Start

```bash
# Install dependencies
poetry install

# Launch TUI
bbctl tui
```

## Features

### 🎛️ Six Interactive Screens

1. **Dashboard (d)** - Overview with live statistics
2. **Scans (s)** - Manage and monitor scans
3. **Activity (v)** - Real-time activity feed
4. **Assets (a)** - Browse discovered assets
5. **Findings (f)** - View security findings
6. **Agents (g)** - Manage scanning agents

### ⚡ Real-time Updates

- WebSocket streaming for instant activity updates
- Auto-refresh for scans, assets, and findings
- Live status indicators
- Pause/resume activity feed

### 🔍 Interactive Filtering

- Text search across all data
- Domain filtering for assets
- Severity filtering for findings (1-5)
- In-scope toggle for assets
- Real-time filter updates

### ⌨️ Keyboard Navigation

**Global Shortcuts:**
- `d` - Dashboard
- `s` - Scans
- `a` - Assets
- `f` - Findings
- `v` - Activity
- `g` - Agents
- `q` - Quit
- `?` - Help

**Common Actions:**
- `r` - Refresh
- `/` - Focus filter
- `Esc` - Clear filter
- `Enter` - View details

## Screen Guide

### Dashboard
Shows live statistics with auto-refresh every 5 seconds:
- Total scans
- Active scans
- Assets discovered
- Findings count
- Agent count

**Actions:**
- `r` - Refresh stats

### Scans Screen
Manage all BBOT scans with filtering and details.

**Table Columns:**
- Name - Scan identifier
- Status - Current state (RUNNING, DONE, etc.)
- Target - Target being scanned
- Preset - Configuration used
- Started - Start timestamp
- Finished - End timestamp
- Duration - How long scan took

**Actions:**
- `n` - Create new scan (coming soon)
- `c` - Cancel selected scan
- `r` - Refresh scan list
- `/` - Filter by name/target
- `Enter` - View scan details

**Auto-refresh:** Every 5 seconds

### Activity Screen
Live feed of all system activities with WebSocket streaming.

**Features:**
- Real-time updates (100 historic activities loaded)
- Auto-scroll to newest
- Color-coded activity types
- Pause/resume functionality
- Activity buffer (1000 items max)

**Actions:**
- `Space` - Pause/resume feed
- `c` - Clear feed
- `r` - Restart stream
- `/` - Filter activities (coming soon)

**Indicator:**
- 🟢 LIVE - Streaming active
- 🟡 PAUSED - Feed paused
- 🔴 OFFLINE - Connection lost

### Assets Screen
Browse discovered assets with filtering.

**Table Columns:**
- Host - IP or domain
- Open Ports - Detected open ports
- Technologies - Identified tech stack
- Cloud - Cloud provider
- Findings - Number of findings
- Modified - Last update

**Actions:**
- `r` - Refresh assets
- `/` - Filter by domain
- `i` - Toggle in-scope only
- `Enter` - View asset details

**Filters:**
- Text: Filter by domain name
- In-Scope: Show only in-scope assets

**Auto-refresh:** Every 10 seconds

### Findings Screen
View security findings with severity filtering.

**Table Columns:**
- Severity - Risk level (color-coded)
- Name - Finding type
- Host - Affected host
- Description - Brief description
- Last Seen - Last detected

**Severity Colors:**
- 🟣 CRITICAL (5)
- 🔴 HIGH (4)
- 🟠 MEDIUM (3)
- 🟡 LOW (2)
- 🔵 INFO (1)

**Actions:**
- `1` - Show INFO and above (all)
- `2` - Show LOW and above
- `3` - Show MEDIUM and above
- `4` - Show HIGH and above
- `5` - Show CRITICAL only
- `/` - Search by name/description
- `r` - Refresh findings
- `Enter` - View finding details

**Auto-refresh:** Every 10 seconds

### Agents Screen
Manage BBOT scanning agents.

**Table Columns:**
- ID - Agent identifier
- Status - Current state
- Last Seen - Last check-in

**Actions:**
- `n` - Create new agent
- `r` - Refresh agent list

**Auto-refresh:** Every 5 seconds

## Configuration

### Server URL
```bash
# Set via command line
bbctl --url http://localhost:8807 tui

# Set via environment variable
export BBOT_SERVER_URL=http://localhost:8807
bbctl tui

# Set in config file (~/.config/bbot_server/config.yml)
url: http://localhost:8807
```

### API Authentication
```bash
# Set via environment variable
export BBOT_SERVER_API_KEY=your-api-key-here

# Or in config file
api_key: your-api-key-here
```

### Debug Mode
```bash
# Enable debug logging
bbctl --debug tui
```

## Keyboard Shortcuts Reference

### Global
| Key | Action | Description |
|-----|--------|-------------|
| `d` | Dashboard | Go to dashboard |
| `s` | Scans | Go to scans screen |
| `a` | Assets | Go to assets screen |
| `f` | Findings | Go to findings screen |
| `v` | Activity | Go to activity feed |
| `g` | Agents | Go to agents screen |
| `q` | Quit | Exit TUI |
| `?` | Help | Show help (coming soon) |

### Common (Most Screens)
| Key | Action | Description |
|-----|--------|-------------|
| `r` | Refresh | Reload current data |
| `/` | Filter | Focus search/filter input |
| `Esc` | Clear | Clear current filter |
| `Enter` | Details | View selected item details |
| `↑/↓` | Navigate | Move selection up/down |
| `PgUp/PgDn` | Page | Page through data |

### Scans Screen
| Key | Action | Description |
|-----|--------|-------------|
| `n` | New Scan | Create new scan (coming soon) |
| `c` | Cancel | Cancel selected scan |

### Activity Screen
| Key | Action | Description |
|-----|--------|-------------|
| `Space` | Pause/Resume | Toggle activity feed |
| `c` | Clear | Clear all activities |

### Findings Screen
| Key | Action | Description |
|-----|--------|-------------|
| `1` | INFO+ | Show INFO and above |
| `2` | LOW+ | Show LOW and above |
| `3` | MEDIUM+ | Show MEDIUM and above |
| `4` | HIGH+ | Show HIGH and above |
| `5` | CRITICAL | Show CRITICAL only |

### Assets Screen
| Key | Action | Description |
|-----|--------|-------------|
| `i` | In-Scope | Toggle in-scope filter |

### Agents Screen
| Key | Action | Description |
|-----|--------|-------------|
| `n` | New Agent | Create new agent |

## Tips & Tricks

### Efficient Navigation
1. Use single-key shortcuts (d/s/a/f/v/g) for quick screen switching
2. Press `/` to immediately start filtering
3. Use `Esc` to quickly clear filters and see all data

### Monitoring Active Scans
1. Go to Activity screen (`v`) to watch real-time updates
2. Use Dashboard (`d`) for high-level overview
3. Check Scans screen (`s`) for detailed status

### Finding Critical Issues
1. Go to Findings screen (`f`)
2. Press `5` to show only CRITICAL findings
3. Use `Enter` to view details
4. Press `4` to include HIGH severity

### Filtering Assets
1. Go to Assets screen (`a`)
2. Press `/` and type domain name
3. Press `i` to toggle in-scope only
4. Use `Enter` to view details

### Activity Feed Management
1. Press `Space` to pause when you see something interesting
2. Press `c` to clear old activities
3. Press `r` to restart the stream

## Troubleshooting

### TUI Won't Launch

**Error:** `ModuleNotFoundError: No module named 'textual'`
```bash
# Solution: Install dependencies
poetry install
```

**Error:** `Connection refused`
```bash
# Solution: Start BBOT server
bbctl server start
```

### Connection Issues

**Problem:** Shows "Error loading data"
```bash
# Check server is running
bbctl server status

# Verify server URL
bbctl --url http://localhost:8807 tui

# Check API key is set
echo $BBOT_SERVER_API_KEY
```

### Activity Feed Not Updating

**Problem:** Activity screen shows "OFFLINE"
```bash
# Check server logs
bbctl server logs

# Restart stream
# Press 'r' in activity screen
```

**Problem:** Feed is paused
```bash
# Resume feed
# Press 'Space' in activity screen
```

### Display Issues

**Problem:** Colors not showing
- Use a terminal with 256-color support
- Try: iTerm2, Terminal.app, gnome-terminal, Windows Terminal

**Problem:** Layout broken
- Increase terminal size (minimum 80x24)
- Use full-screen mode

### Performance Issues

**Problem:** TUI is slow
- Reduce number of items with filters
- Clear activity feed regularly (press `c`)
- Close and reopen TUI

**Problem:** High memory usage
- Activity feed buffers 1000 items max
- Clear feed periodically
- Restart TUI for long-running sessions

## Advanced Usage

### Multiple Servers
```bash
# Connect to different servers
bbctl --url http://server1:8807 tui
bbctl --url http://server2:8807 tui
```

### Filter Syntax (Future Enhancement)
```bash
# Coming soon: Advanced filter syntax
type:NEW_FINDING host:example.com
severity:HIGH domain:target.com
```

### Scripting with TUI
```bash
# Launch TUI in background (not recommended)
# TUI is interactive and should run in foreground

# Use CLI commands for scripting instead
bbctl scan list --json
bbctl asset list --domain example.com --csv
```

## FAQ

**Q: Can I use the TUI remotely over SSH?**
A: Yes! The TUI works perfectly over SSH with proper terminal support.

**Q: Does the TUI work on Windows?**
A: Yes, with Windows Terminal or WSL2.

**Q: Can I customize keyboard shortcuts?**
A: Not yet, but it's planned for a future release.

**Q: How do I export data from the TUI?**
A: Coming soon! For now, use CLI commands:
```bash
bbctl scan list --csv > scans.csv
bbctl finding list --json > findings.json
```

**Q: Can I run multiple TUI instances?**
A: Yes, each instance connects independently to the server.

**Q: How much memory does the TUI use?**
A: Typically 50-100MB, similar to other Textual applications.

**Q: Can I use mouse clicks?**
A: Yes! Textual supports mouse interactions (click buttons, select rows).

**Q: Is there a light theme?**
A: Not yet, but custom themes are planned.

## Getting Help

### In-App Help
- Press `?` for help modal (coming soon)
- Status bars show available actions
- Footer displays active keybindings

### External Resources
- BBOT Server Docs: http://localhost:8807/v1/docs
- Textual Docs: https://textual.textualize.io/
- GitHub Issues: https://github.com/blacklanternsecurity/bbot-server/issues

### Debug Mode
```bash
# Enable verbose logging
bbctl --debug tui

# Check logs
tail -f ~/.config/bbot_server/logs/bbot-server.log
```

## Contributing

Found a bug or want a feature? Please open an issue!

## License

AGPL-3.0 - Same as BBOT Server
