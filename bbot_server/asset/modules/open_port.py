from ._base import BaseAssetModule


class open_port(BaseAssetModule):
    fieldnames = ["open_ports"]

    def absorb_event(self, asset, event):
        print(f"{event.type} / {event.host} / {event.port}")
        if event.port:
            open_ports = set(asset.extra_fields.get("open_ports", []))
            if event.port not in open_ports:
                open_ports.add(event.port)
                asset.add_history_entry(f"Found open port {event.port}", event.timestamp, event.uuid)
                asset.extra_fields["open_ports"] = sorted(open_ports)
