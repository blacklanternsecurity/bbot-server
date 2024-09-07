import importlib
from pathlib import Path

module_dir = Path(__file__).parent

backend_choices = ["http"]
for p in module_dir.iterdir():
    if p.is_file() and p.suffix.lower() == ".py" and not p.stem.startswith("_"):
        backend_choices.append(p.stem)


def BBOTBackend(backend_module, *args, **kwargs):
    package = importlib.import_module(f".backends.{backend_module}", package="bbot_io")
    module = getattr(package, backend_module)
    return module(*args, **kwargs)
