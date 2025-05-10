![Image](https://github.com/user-attachments/assets/f53417ae-1299-4df0-92d0-33cfd34283e1)

[![Python Version](https://img.shields.io/badge/python-3.9+-FF8400)](https://www.python.org) [![License](https://img.shields.io/badge/license-GPLv3-FF8400.svg)](https://github.com/blacklanternsecurity/bbot/blob/dev/LICENSE) [![PyPi Downloads](https://static.pepy.tech/personalized-badge/bbot-server?right_color=orange&left_color=grey)](https://pepy.tech/project/bbot-server) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff) [![Tests](https://github.com/blacklanternsecurity/bbot-server/actions/workflows/tests.yml/badge.svg?branch=stable)](https://github.com/blacklanternsecurity/bbot-server/actions?query=workflow%3A"tests") [![Codecov](https://codecov.io/gh/blacklanternsecurity/bbot-server/branch/stable/graph/badge.svg?token=IR5AZBDM5K)](https://codecov.io/gh/blacklanternsecurity/bbot-server) [![Discord](https://img.shields.io/discord/859164869970362439)](https://discord.com/invite/PZqkgxu5SA)

# BBOT Server [BETA]

***NOTE**: This is an early-access preview of **BBOT Server**. Basic features are documented below. Expect updates as development progresses, including blog posts and documentation describing the full range of features.*

---

BBOT Server is a database and multiplayer hub for all your [BBOT](https://github.com/blacklanternsecurity/bbot) activities!

- [x] **Asset Tracking and Alerting**
    - [x] Get detailed history for each individual asset
    - [ ] Instantly alert on new vulnerabilities, open ports, etc.
- [x] **Scan Management**
    - [x] Kick off concurrent scans on remote servers
    - [x] Monitor scan progress, statistics
- [x] **Collaboration**
    - [x] Multi-user CLI
    - [x] Multiple concurrent scans
- [x] **Advanced Querying**
    - [x] REST API
    - [x] Python SDK
    - [x] Export to JSON/CSV
- [x] [AI interaction via MCP](#MCP)

## Installation

```bash
# clone the repo and cd into it
git clone git@github.com:blacklanternsecurity/bbot-server.git && cd bbot_server

# Install in editable mode
pipx install -e .
```

Note: to update to the latest version, run `git pull` in the `bbot_server` directory.

## Start the server

Note: this requires Docker and Docker Compose to be installed.

```bash
# Start BBOT server using Docker Compose
bbctl server start
```

## Start a scan (direct from BBOT CLI)

You can output a BBOT scan directly to BBOT server:

Note that this requires BBOT 3.0 or later (install with `pipx install git+https://github.com/blacklanternsecurity/bbot@3.0`)

```bash
# Start a BBOT scan, sending output to BBOT server
bbot -t evilcorp.com -p subdomain-enum -om http -c modules.http.url=http://localhost:8807/v1/events/
```

## Ingest events from past BBOT scans

If you forgot to output a scan to BBOT server, you can easily ingest it after the fact:

```bash
# Ingest events from a past scan
cat ~/.bbot/scans/demonic_jimmy/output.json | bbctl event ingest
```

## Start a scan (through BBOT server)

In BBOT server, scans are stored presets that can be run repeatably.

To create a scan, pass a BBOT preset to `scans create`:

```bash
# Create a new scan
bbctl scan create --name "evilcorp_subdomains" --preset my_preset.yml
```

The preset contains your targets, and will look something like this:

```yaml
targets:
  - evilcorp.com
  - evilcorp.net
  - 1.2.3.0/24

blacklist:
  - internal.evilcorp.com

include:
  - subdomain-enum
  - cloud-enum
  - code-enum

modules:
  - nuclei

config:
  - virustotal:
    api_key: deadbeef
```

## Start the scan

```bash
# List scans
bbctl scan list

# Start the scan
bbctl scan start "evilcorp_subdomains"
```

## Monitor scan progress

You can monitor the scan's progress in several ways:

### Tail asset activity:

This will output an activity whenever a change is detected to an asset, e.g. a change in DNS, new open port, vulnerability, or technology.

```bash
# Monitor changes to assets as they are discovered
bbctl activity tail
```

### Tail raw events:

If you'd like, you can also tail the raw events as they stream in from the BBOT scan.

```bash
# Monitor raw BBOT events
bbctl event tail
```

### Check scan status:

You can monitor or stop an in-progress scan:

```bash
# List scan runs
bbctl scan runs list

# Stop the scan
bbctl scan runs stop --name "demonic_jimmy"
```

## Targets

BBOT server categorizes its assets by target.

You can list targets like so:

```bash
# List targets
bbctl target list

# Create a new target
bbctl target create --seeds seeds.txt --blacklist blacklist.txt
```

## Custom triggers

You can kick off a custom command or bash script whenever a certain activity happens, such as when a new technology or open port is discovered.

```bash
# Trigger a custom command whenever a new open port is discovered
bbctl activity tail --json | jq -r 'select(.type == "PORT_OPENED") | .netloc' | while read netloc
do
  echo "New open port at $netloc"
  ./custom_script.sh "$netloc"
done
```

## Alerting

TODO

## Query and Export Data

You can query and export the data even while a scan is running.

### Assets

```bash
# List assets
bbctl asset list

# Export assets to CSV
bbctl asset export --csv > assets.csv

# Export assets as JSON
bbctl asset export --json | jq
```

### Events

```bash
# List events
bbctl event list

# Export events to CSV
bbctl event export --csv > events.csv

# Export events as JSON
bbctl event export --json | jq
```

### Technologies

```bash
# List technologies
bbctl technology list

# List technologies by specific domain
bbctl technology list --domain evilcorp.com
```

### Findings

```bash
# List findings
bbctl finding list

# Search findings for a certain string
bbctl finding list --search "IIS"
```

### Statistics

Overarching statistics are stored for all assets, and can be queried by target or domain.

```bash
# List stats for all assets
bbctl asset stats | jq

# List stats for specific domain
bbctl asset stats --domain evilcorp.com | jq
```

### MCP

BBOT Server supports chat-based AI interaction via MCP (Model Context Protocol).

The SSE server listens at `http://localhost:8807/v1/mcp/`

`mcp.json` (cursor / vs code):
```json
{
    "mcpServers": {
        "bbot": {
            "url": "http://localhost:8807/v1/mcp/"
        }
    }
}
```

After connecting your AI client to BBOT Server, you can ask it sensible questions like, "Use MCP to get all the bbot findings", "what are the top open ports?", "what else can you do with BBOT MCP?", etc.

## Screenshots

*Tailing activities in real time*

![activity-tail](https://github.com/user-attachments/assets/8188f32c-45bc-4f81-bf98-c59adfbdc5df)

*AI Chat interaction via MCP*

![mcp](https://github.com/user-attachments/assets/3997b534-2ed8-4e04-b8c3-a7b42daf4106)

*Scans*

![scan-run-list](https://github.com/user-attachments/assets/d6ffb6e5-06d7-4439-936a-3d2b1a6306ee)

*Technologies*

![technology-list](https://github.com/user-attachments/assets/7b662858-8c08-4bb9-a520-6381d2964dde)

*Findings*

![finding-list](https://github.com/user-attachments/assets/3fcbb977-6d47-4dc1-81b7-a26e8e3bc292)

*REST API*

![rest-api](https://github.com/user-attachments/assets/567bd266-b047-4005-bc0b-22d5bfd2a12b)
