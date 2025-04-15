from pathlib import Path

# make a list of all the applets and their file locations

applet_dir = Path(__file__).parent / "applets"

APPLETS = {}
# Use rglob to recursively find all Python files
for p in applet_dir.rglob("*.py"):
    # Skip files that start with underscore
    if not p.stem.startswith("_") and not p.stem.endswith("_models"):
        APPLETS[p.stem] = p
