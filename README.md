![Image](https://github.com/user-attachments/assets/3cf3fb27-ded3-47b5-8eec-2f8358358ffd)

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
git clone git@github.com:blacklanternsecurity/bbot-server.git && cd bbot-server

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

## Interacting with BBOT Server Remotely (Multiplayer)

By default, BBOT Server listens on localhost. Use `--listen` to expose it to the network:

```bash
bbctl server start --listen 0.0.0.0
```

### Authentication

The first time you start BBOT Server, an API key will be auto generated and put into `~/.config/bbot_server/config.yml`:

```yaml
# ~/.config/bbot_server/config.yml

# list of API keys to be considered valid
api_keys:
  - 4aa8b3c2-9b4d-4208-890c-4ce9ad3b4710
```

The `api_keys` value in `config.yml` is used by both the server (as a database of valid API keys), and by the client (it will pick one from the list and use it). Normally it just works and you don't have to mess with it. But to access BBOT Server remotely, you'll need to copy the API key from the server onto your local system, along with its URL:

```yaml
# ~/.config/bbot_server/config.yml
url: http://1.2.3.4:8807/v1/
api_keys:
  - deadbeef-9b4d-4208-890c-4ce9ad3b4710
```

This tells `bbctl` (the client) where the server is, and gives it the means to authenticate.

### Adding and Revoking API Keys

API keys can be added and removed if you are on the server machine:

```bash
# add an API key
bbctl server apikey add

# list API keys
bbctl server apikey list

# revoke an API key
bbctl server apikey delete deadbeef-9b4d-4208-890c-4ce9ad3b4710
```

## Send a BBOT Scan to the Server

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

To start a scan in BBOT server, you need to first create a **Preset** and **Target**.

1. Create Preset

The preset defines which flags, modules, API keys, etc. will be used for the scan. It typically looks something like this:

**`my_preset.yml`**:
```yaml
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

```bash
# create a new scan preset
bbctl scan preset create my_preset.yml
```

2. Create Target

A target defines what's in-scope for the scan. They can also be used when filtering assets.

```bash
# create a new scan target
bbctl scan target create --seeds evilcorp.txt --name "my_target"
```

3. Start Scan

Now that we've created a preset and target, we can start the scan:

```bash
# start the scan
bbctl scan start --preset my_preset --target my_target --name "demonic_jimmy"
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
bbctl scan list

# Stop the scan
bbctl scan cancel "demonic_jimmy"
```

## Targets

BBOT server categorizes its assets by target.

You can list targets like so:

```bash
# List targets
bbctl target list

# Create a new target
bbctl target create --seeds seeds.txt --blacklist blacklist.txt --name custom_target

# List only the assets that match your new target
bbctl asset list --target custom_target
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
bbctl asset list --csv > assets.csv

# Export assets as JSON
bbctl asset list --json | jq
```

### Events

```bash
# List events
bbctl event list

# Export events to CSV
bbctl event list --csv > events.csv

# Export events as JSON
bbctl event list --json | jq
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
