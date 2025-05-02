![Image](https://github.com/user-attachments/assets/c63cc32c-8823-4b60-a990-12b544dd99ba)

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
- [x] AI interaction via MCP

## Installation

```bash
# clone the repo and cd into it
git clone git@github.com:blacklanternsecurity/bbot_server.git && cd bbot_server

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

**Tail asset activity**:

This will output an activity whenever a change is detected to an asset, e.g. a change in DNS, new open port, vulnerability, or technology.

```bash
# Monitor changes to assets as they are discovered
bbctl activity tail
```

**Tail raw events**:

If you'd like, you can also tail the raw events as they stream in from the BBOT scan.

```bash
# Monitor raw BBOT events
bbctl event tail
```

**Check scan status**:

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
```

You can create a target manually:

## Custom triggers

You can set up custom triggers. When a certain activity happens, you can kick off a custom command or bash script.

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

## View/export the data

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

# Search findings for a certain 
```

### Statistics

Overarching statistics are stored for all assets, and can be queried by target or domain.

```bash
# List stats for all assets
bbctl asset stats | jq

# List stats for specific domain
bbctl asset stats --domain evilcorp.com | jq
```

## Screenshots

*Launch and monitor concurrent scans*

![scans](https://github.com/user-attachments/assets/7644809f-e111-49f8-b627-c0c77a65110a)

*Realtime asset monitoring*

![monitor-assets](https://github.com/user-attachments/assets/ed7ac9f2-34e8-4770-a971-49fdf7f77bea)

*REST API*

![rest-api](https://github.com/user-attachments/assets/567bd266-b047-4005-bc0b-22d5bfd2a12b)
