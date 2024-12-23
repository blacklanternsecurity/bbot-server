import importlib
from pathlib import Path

module_dir = Path(__file__).parent

CUSTOM_FIELDNAMES = []

ASSET_MODULES = {}
for p in module_dir.iterdir():
    if p.is_file() and p.suffix.lower() == ".py" and not p.stem.startswith("_"):
        module = p.stem
        package = importlib.import_module(f".asset.modules.{module}", package="bbot_server")
        module_class = getattr(package, module)
        module_obj = module_class()
        ASSET_MODULES[module] = module_obj
        for field in module_obj.fieldnames:
            if field in CUSTOM_FIELDNAMES:
                raise ValueError(f"Field {field} already exists")
            CUSTOM_FIELDNAMES.append(field)
