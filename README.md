![bbot-server](https://github.com/user-attachments/assets/3041001f-5135-4f69-a585-fea30341d803)

# BBOT Server

<!-- ![bbot-server](https://github.com/user-attachments/assets/f97648ad-fc72-4fbf-8f85-3896b9f8f02c) -->

BBOT Server is a central database and multiplayer hub for all your [BBOT](https://github.com/blacklanternsecurity/bbot) scanning activities!

- [x] **Scan Management**
    - [x] Kick off concurrent scans on remote servers
    - [x] Monitor scan progress, statistics
- [x] **Asset Tracking and Alerting**
    - [x] Detailed history for each individual asset
    - [ ] Instant alerting on new vulnerabilities, open ports, etc.
- [x] **Collaboration**
    - [x] Multi-user CLI
    - [x] Multiple concurrent scans
- [x] **Advanced Querying**
    - [x] REST API
    - [x] Python SDK

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

BBOT server categorizes its assets by target. If you previously created a scan from a preset, a target was automatically created.

You can list targets like so:

```bash
# List targets
bbctl target list
```

You can create a target manually:

## Custom triggers

TODO

## Alerting

TODO

## View/export the data

You can query and export the data even while a scan is running.

**List assets**:

```bash
# List assets
bbctl asset list

# Export assets to CSV
bbctl asset export --csv > assets.csv

# Export assets as JSON
bbctl asset export --json | jq
```

**List events**:

```bash
# List events
bbctl event list

# Export events to CSV
bbctl event export --csv > events.csv

# Export events as JSON
bbctl event export --json | jq
```

## Screenshots

*Scan editor (terminal UI)*

![scan-editor](https://github.com/user-attachments/assets/9c31d2ef-f4f0-4d65-bd45-263a8d16bd7f)

*Launch and monitor concurrent scans*

![scans](https://github.com/user-attachments/assets/7644809f-e111-49f8-b627-c0c77a65110a)

*Realtime asset monitoring*

![monitor-assets](https://github.com/user-attachments/assets/ed7ac9f2-34e8-4770-a971-49fdf7f77bea)

*REST API*

![rest-api](https://github.com/user-attachments/assets/567bd266-b047-4005-bc0b-22d5bfd2a12b)
