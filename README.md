![bbot-server](https://github.com/user-attachments/assets/3041001f-5135-4f69-a585-fea30341d803)

# BBOT Server

<!-- ![bbot-server](https://github.com/user-attachments/assets/f97648ad-fc72-4fbf-8f85-3896b9f8f02c) -->

BBOT Server is your central command center for all your nefarious [BBOT](https://github.com/blacklanternsecurity/bbot) activities!

- [x] **Scan Management**
    - [ ] Kick off concurrent scans on remote servers
    - [x] Monitor scan progress, statistics
- [x] **Asset Tracking and Alerting**
    - [x] Detailed history for each individual asset
    - [ ] Instant alerting on new vulnerabilities, open ports, etc.
- [x] **Collaboration**
    - [x] Multi-user CLI
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

# monitor new event activity
bbctl events tail

# list scan status
bbctl scans runs
```

## Screenshots

![scan-editor](https://github.com/user-attachments/assets/9c31d2ef-f4f0-4d65-bd45-263a8d16bd7f)

*Scan editor (terminal UI)*

![rest-api](https://github.com/user-attachments/assets/567bd266-b047-4005-bc0b-22d5bfd2a12b)

*REST API*

![monitor-assets](https://github.com/user-attachments/assets/ed7ac9f2-34e8-4770-a971-49fdf7f77bea)

*Realtime asset monitoring*

![scans](https://github.com/user-attachments/assets/7644809f-e111-49f8-b627-c0c77a65110a)

*Launch and monitor concurrent scans*
