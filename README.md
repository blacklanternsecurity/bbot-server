![Image](https://github.com/user-attachments/assets/3cf3fb27-ded3-47b5-8eec-2f8358358ffd)

[![Python Version](https://img.shields.io/badge/python-3.9+-FF8400)](https://www.python.org) [![License](https://img.shields.io/badge/license-AGPLv3-FF8400.svg)](https://github.com/blacklanternsecurity/bbot/blob/dev/LICENSE) [![PyPi Downloads](https://static.pepy.tech/personalized-badge/bbot-server?right_color=orange&left_color=grey)](https://pepy.tech/project/bbot-server) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff) [![Tests](https://github.com/blacklanternsecurity/bbot-server/actions/workflows/tests.yml/badge.svg?branch=stable)](https://github.com/blacklanternsecurity/bbot-server/actions?query=workflow%3A"tests") [![Codecov](https://codecov.io/gh/blacklanternsecurity/bbot-server/branch/stable/graph/badge.svg?token=IR5AZBDM5K)](https://codecov.io/gh/blacklanternsecurity/bbot-server) [![Discord](https://img.shields.io/discord/859164869970362439)](https://discord.com/invite/PZqkgxu5SA)

# BBOT Server [BETA]

***NOTE**: This is an early-access preview of **BBOT Server**. Basic features are documented below. Expect updates as development progresses, including blog posts and documentation describing the full range of features.*

---

BBOT Server is a database and multiplayer hub for all your [BBOT](https://github.com/blacklanternsecurity/bbot) activities!

- [x] **Asset Tracking and Alerting**
    - [x] Get detailed history for each individual asset
    - [ ] Instantly alert on new vulnerabilities, open ports, etc.
- [x] **Collaboration**
    - [x] Multi-user CLI
- [x] **Advanced Querying**
    - [x] REST API
    - [x] Python SDK
    - [x] Export to JSON/CSV
- [x] [AI interaction via MCP](#MCP)

## Installation

```bash
# install with uv (recommended)
uv tool install bbot-server

# or with pipx
pipx install bbot-server
```

To install `uv`, see the [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/).

### From source (for development)

```bash
git clone git@github.com:blacklanternsecurity/bbot-server.git && cd bbot-server
uv sync
```

Note: to update to the latest version, run `git pull && uv sync` in the `bbot-server` directory.

When installed from source, commands shown below as `bbctl` can be run with `uv run bbctl` from the project directory, or you can activate the virtual environment first with `source .venv/bin/activate`.

## Start the server

Note: this requires Docker and Docker Compose to be installed.

```bash
# Start BBOT server using Docker Compose (pulls from Docker Hub)
bbctl server start
```

### Development mode

When working on the bbot-server source code, use `--dev` to build from source and mount your code for live reload:

```bash
# From the bbot-server repo root
bbctl server --dev start
```

The `--dev` flag works with all server subcommands (`start`, `stop`, `down`, `logs`, `status`, `compose`).

## Deploy with Helm (Kubernetes)

BBOT Server can be deployed to Kubernetes using its official Helm chart. The chart deploys the API server, worker, MongoDB, and Redis.

### Quick Start

```bash
# Add the Helm repo
helm repo add blacklanternsecurity https://blacklanternsecurity.github.io/bbot-server

# Install
helm install bbot blacklanternsecurity/bbot-server
```

Or install directly from the OCI registry:

```bash
helm install bbot oci://registry-1.docker.io/blacklanternsecurity/bbot-server
```

### Configuration

Key values can be overridden with `--set` or a custom values file:

```bash
helm install bbot blacklanternsecurity/bbot-server \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host=bbot.example.com \
  --set ingress.hosts[0].paths[0].path=/ \
  --set ingress.hosts[0].paths[0].pathType=Prefix
```

Or with a values file:

```yaml
# custom-values.yaml
ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt
  hosts:
    - host: bbot.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: bbot-tls
      hosts:
        - bbot.example.com

secrets:
  # provide your own API key, or leave empty to auto-generate
  apiKey: ""
```

```bash
helm install bbot blacklanternsecurity/bbot-server -f custom-values.yaml
```

### Retrieving the API Key

If you didn't provide an API key, one is auto-generated. Retrieve it with:

```bash
kubectl get secret bbot-api-key -o jsonpath='{.data.api-key}' | base64 -d
```

### Upgrading

```bash
helm repo update
helm upgrade bbot blacklanternsecurity/bbot-server
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
  - deadbeef-9b4d-4208-890c-4ce9ad3b4710
```

The `api_keys` value in `config.yml` is used by both the server (as a database of valid API keys), and by the client (it will pick one from the list and use it). Normally it just works and you don't have to mess with it. But to access BBOT Server remotely, you'll need to copy the API key from the server onto your local system, along with its URL:

```yaml
# ~/.config/bbot_server/config.yml
url: http://1.2.3.4:8807/v1/
api_keys:
  - deadbeef-9b4d-4208-890c-4ce9ad3b4710
```

This tells `bbctl` (the client) where the server is, and gives it the means to authenticate.

To utilise the API key and interact with the BBOT Server via the HTTP API, set the `X-API-Key` HTTP header to the value of a valid API key.

### Environment Variables

BBOT Server can be configured via environment variables, which is useful for Docker deployments or CI/CD pipelines. The configuration uses a nested structure with double underscores (`__`) as delimiters.

All environment variables use the prefix `BBOT_SERVER_`.

#### Examples

```bash
# Server URL
export BBOT_SERVER_URL="http://localhost:8807/v1/"

# Authentication
export BBOT_SERVER_AUTH_ENABLED=true
export BBOT_SERVER_AUTH_HEADER="X-API-Key"
export BBOT_SERVER_API_KEY="deadbeef-9b4d-4208-890c-4ce9ad3b4710"

# Database URIs (nested configs)
export BBOT_SERVER_EVENT_STORE__URI="mongodb://localhost:27017/bbot_server"
export BBOT_SERVER_ASSET_STORE__URI="mongodb://localhost:27017/bbot_server"
export BBOT_SERVER_USER_STORE__URI="mongodb://localhost:27017/bbot_server"

# Message Queue URI (standalone Redis)
export BBOT_SERVER_MESSAGE_QUEUE__URI="redis://localhost:6379/0"

# Message Queue URI (Redis Cluster - use redis+cluster:// scheme)
export BBOT_SERVER_MESSAGE_QUEUE__URI="redis+cluster://your-redis-cluster-entrypoint:6379/0"

# Agent configuration
export BBOT_SERVER_AGENT__BASE_PRESET='{"modules": ["nmap"]}'

# CLI configuration
export BBOT_SERVER_CLI__HTTP_TIMEOUT=90

# Module-specific configuration (double-nested)
export BBOT_SERVER_MODULES__SOME_MODULE__SOME_OPTION="value"
```

Note the double underscores (`__`) used to access nested configuration fields. This is required by the Pydantic settings framework.

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

You can output a BBOT scan directly to BBOT server with the following preset:

```yaml
# bbot-server.yml

output_modules:
  - http

config:
  modules:
    http:
      # URL of BBOT Server
      url: http://localhost:8807/v1/events/
      # API Key header
      headers:
        x-api-key: deadbeef-9b4d-4208-890c-4ce9ad3b4710
```

Note that this requires BBOT 3.0 or later (install with `pipx install git+https://github.com/blacklanternsecurity/bbot@3.0`)

```bash
# Start a BBOT scan, sending output to BBOT server
bbot -t evilcorp.com -p subdomain-enum ./bbot-server.yml
```

## Ingest events from past BBOT scans

If you forgot to output a scan to BBOT server, you can easily ingest it after the fact:

```bash
# Ingest events from a past scan
cat ~/.bbot/scans/demonic_jimmy/output.json | bbctl event ingest
```

Note that this requires BBOT 3.0 or later (install with `pipx install git+https://github.com/blacklanternsecurity/bbot@3.0`)

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
      modules:
        virustotal:
          api_key: deadbeef
    ```

    ```bash
    # create a new scan preset
    bbctl scan preset create my_preset.yml
    ```

    For more guidance and examples on presets, check out the [bbot docs](https://www.blacklanternsecurity.com/bbot/Stable/scanning/presets/).

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


## Terminal User Interface (TUI)

BBOT Server includes an interactive Terminal User Interface built with [Textual](https://textual.textualize.io/). The TUI provides a real-time dashboard for querying assets, findings, events, etc. It runs in the terminal but behaves similarly to a web app, with clickable buttons, scrollable tables, and even a light and dark theme.

![bbctl ui dark](https://github.com/user-attachments/assets/8c3147d1-e5e6-4f6f-8df7-c174998a45bc)

![bbctl ui light](https://github.com/user-attachments/assets/3abfe9ba-dbb3-45e5-a77a-10d0e04ef0af)

Thanks to [@k11h-de](https://github.com/k11h-de) for implementing this feature!

### Launch the TUI

```bash
bbctl ui
```

### Screens Overview

| Screen | Shortcut | Description |
|--------|----------|-------------|
| **Dashboard** | `d` | Live stats, recent findings (by severity), and recent scans |
| **Scans** | `s` | Manage scan runs—start, cancel, filter, and view details |
| **Activity** | `v` | Real-time WebSocket feed of scan events with pause/resume |
| **Assets** | `a` | Browse and filter discovered assets by domain, target, or in-scope status |
| **Findings** | `f` | View and filter security findings by severity (CRITICAL → INFO) |
| **Agents** | `g` | List, create, and manage BBOT agents |

## Targets

BBOT server categorizes its assets by target.

You can list targets like so:

```bash
# List targets
bbctl scan target list

# Create a new target
bbctl scan target create --seeds seeds.txt --blacklist blacklist.txt --name custom_target

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

The SSE server listens at `http://localhost:8807/v1/mcp/`.

`mcp.json` (Cursor / VS Code):
```json
{
  "mcpServers": {
    "bbot": {
      "url": "http://localhost:8807/v1/mcp/",
      "headers": {
        "x-api-key": "deadbeef-9b4d-4208-890c-4ce9ad3b4710"
      }
    }
  }
}
```

After connecting your AI client to BBOT Server, you can ask it sensible questions like, "Use MCP to get all the bbot findings", "what are the top open ports?", "what else can you do with BBOT MCP?", etc.

**NOTE**: Authentication is [currently broken](https://github.com/blacklanternsecurity/bbot-server/issues/52) in Cursor, Cline, and it seems most other VS Code forks. A workaround is to disable authentication with `--no-authentication` when starting the server. Obviously, be careful with this and don't be a dumbass.

```bash
bbctl server start --no-authentication
```

## As a Python Library

You can interact fully with BBOT Server as a Python library. It supports either local or remote connections, and the interface to both is identical:

### Asynchronous

```python
import asyncio
from bbot_server import BBOTServer

async def main():
    # talk directly to local MongoDB + Redis
    bbot_server = BBOTServer(interface="python")

    # or to a remote BBOT Server instance (config must contain a valid API key)
    bbot_server = BBOTServer(interface="http", url="http://bbot:8807/v1/")

    # one-time setup
    await bbot_server.setup()

    hosts = await bbot_server.get_hosts()
    print(f"hosts: {hosts}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Synchronous

```python
from bbot_server import BBOTServer

if __name__ == "__main__":
    # talk directly to local MongoDB + Redis
    bbot_server = BBOTServer(interface="python", synchronous=True)

    # or to a remote BBOT Server instance (config must contain a valid API key)
    bbot_server = BBOTServer(interface="http", url="http://bbot:8807/v1/", synchronous=True)

    # one-time setup
    bbot_server.setup()

    hosts = bbot_server.get_hosts()
    print(f"hosts: {hosts}")
```

## Running Tests

When running tests, first start MongoDB and Redis via Docker:

```bash
docker run --ulimit nofile=64000:64000 --rm -p 127.0.0.1:27017:27017 mongo
docker run --rm -p 6379:6379 redis
```

Then execute `pytest`:

```bash
# run all tests
uv run pytest -v

# run specific tests
uv run pytest -v -k test_applet_scans
```

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

Connect to the default URL at [http://localhost:8807](http://localhost:8807/) to view and use the interactive API documentation.

![rest-api](https://github.com/user-attachments/assets/567bd266-b047-4005-bc0b-22d5bfd2a12b)
