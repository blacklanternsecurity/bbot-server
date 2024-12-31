# Asset Modules

Most of BBOT server's functionality revolves around assets.

Because of this, assets support custom modules that process events and modify assets in unique ways. Examples of asset modules include:

- open ports
- vulnerabilities
- protocols
- technologies
- etc.

Each asset module is a python class that implements two methods:

- `absorb_event()` - this is called when an event is received and the asset module should process it
    - Here, it will modify the associated asset, such as adding a port, vulnerability, etc.
- `archive_event()` - this is called when an event is archived.
    - Here is where any stale ports/vulns/etc. are removed from the asset.
