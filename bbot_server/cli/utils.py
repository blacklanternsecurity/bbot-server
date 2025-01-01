import sys
from rich.console import Console


class BBCTL_GLOBALS:
    silent = False
    color = True


stdout = Console(file=sys.stdout)
stderr = Console(file=sys.stderr)
