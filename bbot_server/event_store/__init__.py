from pathlib import Path

module_dir = Path(__file__).parent

BACKEND_CHOICES = []
for p in module_dir.iterdir():
    if p.is_file() and p.suffix.lower() == ".py" and not p.stem.startswith("_"):
        BACKEND_CHOICES.append(p.stem)
BACKEND_CHOICES.sort()


def EventStore(config, **kwargs):
    # backend = backend.strip().lower()
    # if backend not in BACKEND_CHOICES:
    #     raise ValueError(f"Invalid event store backend: {backend} - choices: {', '.join(BACKEND_CHOICES)}")
    # import importlib

    # package = importlib.import_module(f".event_store.{backend}", package="bbot_server")
    # module = getattr(package, backend)
    # return module(**kwargs)
    from bbot_server.event_store.mongo import MongoEventStore

    return MongoEventStore(config)
