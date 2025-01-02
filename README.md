# BBOT Server

![bbot-server](https://github.com/user-attachments/assets/3041001f-5135-4f69-a585-fea30341d803)

<!-- ![bbot-server](https://github.com/user-attachments/assets/f97648ad-fc72-4fbf-8f85-3896b9f8f02c) -->

BBOT Server is your central command center for all [BBOT](https://github.com/blacklanternsecurity/bbot) activities!

- [ ] **Scan Management**
    - [ ] Kick off concurrent scans on remote servers
    - [ ] Monitor scan progress, statistics
- [ ] **Asset Tracking and Alerting**
    - [ ] Detailed history for each individual asset
    - [ ] Instant alerting on new vulnerabilities, open ports, etc.
- [ ] **Collaboration**
    - [ ] Multi-user CLI
- [ ] **Advanced Querying**
    - [ ] REST API
    - [ ] Python SDK
    - [ ] GraphQL

```bash
# Start message queue
docker run -d --rm -p 4222:4222 nats

# Start mongodb
docker run -d --rm -p 27017:27017 mongo

# Start bbot server
bbot-server
```

## Basic Workflows

### Insert New Events

- [ ] Run BBOT scan, save events to **Event Store**
- [ ] BBOT Server's **Event Store Monitor** continuously queries the **Event Store** for new events
    - [ ] `NEW_EVENT` event is triggered
        - [ ] Existing asset (w/ matching host) is queried, a copy created, and updated with new data
            - [ ] Asset history is updated with the difference between the old and new asset
        - [ ] This is where **Asset Modules** can hook in to update the asset

### Archive Old Events

- [ ] Periodically (e.g. every 24 hours), **Event Archiver** is run
    - [ ] Every asset is retrieved. For each one, the **Event Archiver** deletes older events and runs a diff.
        - [ ] Event history is updated with the difference between the old and new asset

---

How should we build this?

The core of this whole thing is the asset database. That's where most of the code will be.

The task scheduled will need to be a separate process, for sure. 

How much code will be shared between the Event Store Monitor and the Event Archiver?
    - They are basically the same thing
    - Should they run in the same process?
    - Does it make sense to piggyback them both off the same task scheduler? Or 

Okay let's talk about the task scheduler. First order of business, do we need a legit message queue? It might complicate things, but it would give us things like persistence, and let us queue up things between processes.
    - Probably a must


Plan of attack:

- [x] Build an Event Store (allow inserting events)
- [x] Build an Asset class
    - [x] History (actually just a list of asset activities)
- [x] Message queue
    - [ ] Task scheduler
        - [ ] Event store monitor
            - [ ] Event ingestor
            - [ ] Event archiver


Subcommands:
- [x] `bbctl asset`
    - [x] `bbctl asset tail`
    - [x] `bbctl asset list`
- [x] `bbctl server start/stop`
- [ ] `bbctl target list/add/edit/delete`
    - textual ui copy/paste
