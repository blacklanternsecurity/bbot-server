![bbot-server](https://github.com/user-attachments/assets/3041001f-5135-4f69-a585-fea30341d803)

# BBOT Server

<!-- ![bbot-server](https://github.com/user-attachments/assets/f97648ad-fc72-4fbf-8f85-3896b9f8f02c) -->

BBOT Server is a central command center for all your [BBOT](https://github.com/blacklanternsecurity/bbot) activities!

- [x] **Scan Management**
    - [ ] Kick off concurrent scans on remote servers
    - [x] Monitor scan progress, statistics
- [x] **Asset Tracking and Alerting**
    - [x] Detailed history for each individual asset
    - [ ] Instant alerting on new vulnerabilities, open ports, etc.
- [x] **Collaboration**
    - [x] Multi-user CLI
    - [ ] Multiple concurrent scans
- [x] **Advanced Querying**
    - [x] REST API
    - [x] Python SDK
    - [ ] GraphQL

## Example Usage

```bash
# Start bbot server
bbctl server start

# Create a new scan
bbctl scans create

# Start the scan
bbctl scans start demonic_jimmy

# monitor new asset activity
bbctl assets tail
bbctl assets list

# monitor new event activity
bbctl events tail
bbctl events list

# list scan status
bbctl scans runs
```

## Screenshots

![scan-editor](https://github.com/user-attachments/assets/9c31d2ef-f4f0-4d65-bd45-263a8d16bd7f)

*Scan editor (terminal UI)*

![scans](https://github.com/user-attachments/assets/7644809f-e111-49f8-b627-c0c77a65110a)

*Launch and monitor concurrent scans*

![monitor-assets](https://github.com/user-attachments/assets/ed7ac9f2-34e8-4770-a971-49fdf7f77bea)

*Realtime asset monitoring*

![rest-api](https://github.com/user-attachments/assets/567bd266-b047-4005-bc0b-22d5bfd2a12b)

*REST API*

## How it works

Two types of components make up BBOT server: **Applets** and **Watchdogs**.

### Applets

Applets are the main interface into the database. They allow convenient querying and updating of data via the Python or REST API.

Examples of applets include:

- `Assets` - Query assets.
    - `Open_Ports` - Query open ports.
    - `Vulnerabilities` - Track discovered vulnerabilities over time.
    - `Technologies` - Track discovered technologies over time.
    - `Emails` - Query discovered emails.
    - `Export` - Export assets to CSV, JSON, etc.
    - `Web_Screenshots` - Query web screenshots.
- `Scans` - Manage BBOT scans.
    - `Targets` - Manage scan targets.
    - `Agents` - Manage BBOT scan agents.

- Each applet's functionality is exposed via a collection of API functions like `get_subdomains()`, `get_webscreenshots()`, etc., which double as FastAPI endpoints.
- Applets can be nested beneath other applets, allowing for tidy organization.

Each applet is a single python file in `bbot_server/applets/`. It's common for an applet to have a companion watchdog which updates and maintains the data they expose via the API. Typically, an applet and its watchdog will share a Pydantic model. 

### Watchdogs

Watchdogs are backend-centric tasks. They can be triggered by events, asset activities, or on a schedule. For performance reasons, they run in a dedicated process, and are responsible for watching queues and maintaining the database. Examples of watchdogs include:

- `Open_Ports`
- `Event_Watcher` - Consumes new scan events from the queue, and inserts them into the database.
- `Notifier` - Listens for new changes to assets, and sends notifications to the user via Teams, Discord, etc.
- `Scope_Keeper` - Ensures assets in the database are up to date with the current scope.
- `Archiver` - Periodically archives old scans.
- `Scan_Runner` - Periodically kicks off new scans.

- Watchdogs can listen for new BBOT events, and ingest them via `handle_event()`. Some applets, like `Open_Ports`, use this information to update the associated asset, while others like `Vulnerabilities` have their own dedicated database table.

Watchdogs are dependent on their applets, not the other way around. It makes use of the applet's functions to query/update the database. Each watchdog is a single python file underneath `bbot_server/watchdogs/`.
