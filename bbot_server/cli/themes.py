import typer
from textual.theme import Theme

COLOR = "bold dark_orange"
DARK_COLOR = "grey50"

# textual theme
TEXTUAL_THEME = Theme(
    name="bbot",
    primary="#000000",
    secondary="#1a1a1a",
    accent="#FF8400",
    warning="#FF8400",
    error="#ff4500",
    success="#FF8400",
    foreground="#ffffff",
)

# typer theme
typer.rich_utils.STYLE_OPTION = "bold dark_orange"
typer.rich_utils.STYLE_NEGATIVE_OPTION = "bold red"
typer.rich_utils.STYLE_NEGATIVE_SWITCH = "bold red"
typer.rich_utils.STYLE_SWITCH = "bold orange1"
typer.rich_utils.STYLE_USAGE = "bright_white"
typer.rich_utils.STYLE_METAVAR = "bold dark_orange"
typer.rich_utils.STYLE_OPTION_ENVVAR = "dim orange1"
typer.rich_utils.STYLE_COMMANDS_TABLE_FIRST_COLUMN = "bold dark_orange"
