import importlib
from pathlib import Path

module_dir = Path(__file__).parent

INTERFACES = {}

for p in module_dir.iterdir():
    if p.is_file() and p.suffix.lower() == ".py" and not p.stem.startswith("_"):
        interface = p.stem
        package = importlib.import_module(f".interfaces.{interface}", package="bbot_server")
        interface_class = getattr(package, interface)
        INTERFACES[interface] = interface_class


def BBOTServer(interface="python", **kwargs):
    interface = interface.strip().lower()
    if interface not in INTERFACES:
        raise ValueError(f"Invalid interface: '{interface}' - must be one of {', '.join(sorted(INTERFACES))}")
    interface_class = INTERFACES[interface]
    return interface_class(**kwargs)
