import importlib
from pathlib import Path

module_dir = Path(__file__).parent

module_choices = []
for p in module_dir.iterdir():
    if p.is_file() and p.suffix.lower() == ".py" and p.stem not in ("base", "__init__"):
        module_choices.append(p.stem)


def IO(io_module, *args, **kwargs):
    package = importlib.import_module(f".modules.{io_module}", package="bbot_io")
    module = getattr(package, io_module)
    return module(*args, **kwargs)
