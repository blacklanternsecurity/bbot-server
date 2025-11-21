import json
import yaml
import inspect
import logging
from rich.syntax import Syntax
from typer import Typer, Option  # noqa
from typing import Annotated  # noqa
from functools import cached_property, wraps

from bbot_server.config import BBOT_SERVER_CONFIG as bbcfg
from bbot_server.utils.misc import timestamp_to_human, seconds_to_human


# decorator to register valid agent commands
def subcommand(**kwargs):
    def decorator(fn):
        fn._subcommand = kwargs
        return fn

    return decorator


class BaseBBCTL:
    """
    Base class for all BBCTL commands and subcommands
    """

    command = ""
    # longer description listed above the command's --help
    help = ""
    # short description listed alongside command in the parent's --help
    short_help = ""
    # optional description listed below the command's --help
    epilog = ""

    # which other BBCTL class should include this one
    attach_to = ""

    # BBOT server config helpers
    bbcfg = bbcfg

    # allow the command to be invoked without a subcommand
    _invoke_without_command = False

    # imports for convenience
    import sys
    import orjson
    from rich.table import Table
    from bbot_server.cli.themes import COLOR, DARK_COLOR
    from bbot_server.errors import BBOTServerError, BBOTServerValueError, BBOTServerNotFoundError

    def __init__(self, parent=None):
        self.log = logging.getLogger(f"bbot_server.cli.bbctl.{self.__class__.__name__.lower()}")
        self.parent = parent
        self.children = {}

        # initialize typer
        self.typer = Typer(
            help=self.help,
            short_help=self.short_help,
            epilog=self.epilog,
            invoke_without_command=self._invoke_without_command,
            no_args_is_help=True,
        )

        # register main method
        decorator = self.typer.callback()

        @wraps(self.main)
        def _typer_main(*args, **kwargs):
            self.setup()
            return self.main(*args, **kwargs)

        decorator(_typer_main)

        methods = [method for _, method in inspect.getmembers(self) if callable(method)]
        # register subcommands
        for method in methods:
            command_args = getattr(method, "_subcommand", None)
            if command_args is not None:
                decorator = self.typer.command(**command_args)
                decorator(method)

        # register child classes
        from bbot_server.modules import CLI_MODULES

        # which other cli modules should this one include
        commands_to_include = CLI_MODULES.get(self.command, {})
        for included_bbctl_command in sorted(commands_to_include):
            self.log.debug(f"Including {included_bbctl_command}")
            try:
                bbctl_class = commands_to_include[included_bbctl_command]
            except KeyError:
                raise self.BBOTServerValueError(
                    f'CLI module {self.__class__.__name__} tried to include unknown BBCTL command "{included_bbctl_command}" (options: {",".join(sorted(commands_to_include))})'
                )
            for required_attr in ("command", "help", "short_help"):
                val = getattr(bbctl_class, required_attr, "")
                if not val:
                    raise self.BBOTServerValueError(
                        f"CLI module {bbctl_class.__name__} must define .{required_attr} attribute"
                    )
            child = bbctl_class(parent=self)
            self.children[child.command] = child
            self.typer.add_typer(child.typer, name=child.command)

    # main method, for when the command is executed without any subcommands
    # override this method in subclasses
    def main(self):
        pass

    def setup(self):
        """
        Perform any setup required for the command
        """
        pass

    @property
    def bbot_server(self):
        return self.root.bbot_server

    @property
    def config(self):
        return self.root._config

    def _typer_main(self, *args, **kwargs):
        self.setup()
        self.main(*args, **kwargs)

    @cached_property
    def root(self):
        bbctl = self
        while getattr(bbctl, "parent", None) is not None:
            bbctl = bbctl.parent
        return bbctl

    @property
    def stdout(self):
        return self.root._stdout

    @property
    def stderr(self):
        return self.root._stderr

    def all_children(self, include_self=False):
        children = []
        if include_self:
            children.append(self)
        for child in self.children.values():
            children.append(child)
            children.extend(child.all_children(include_self=True))
        return children

    @property
    def json_highlighter(self):
        return self.root._json_highlighter

    def highlight_json(self, data, **kwargs):
        """
        Highlight a JSON string with rich
        """
        if not isinstance(data, str):
            data = json.dumps(data, indent=2)
        return Syntax(data, "json", theme="monokai", background_color="default", **kwargs)

    def highlight_yaml(self, data, **kwargs):
        """
        Highlight a YAML string with rich
        """
        if not isinstance(data, str):
            data = yaml.safe_dump(data, indent=2, sort_keys=False)
        if not "background_color" in kwargs:
            kwargs["background_color"] = "default"
        if not "theme" in kwargs:
            kwargs["theme"] = "monokai"
        return Syntax(data, "yaml", **kwargs)

    def print_yaml(self, data, **kwargs):
        self.stdout.print(self.highlight_yaml(data, **kwargs))

    def print_pydantic_json(self, model, colorize=False):
        """
        Print a Pydantic model as JSON, with optional highlighting
        """
        if colorize:
            self.stdout.print(self.highlight_json(json.dumps(model.model_dump(), indent=2)))
        else:
            self.print_raw_line(self.orjson.dumps(model.model_dump()))

    def print_json(self, data, colorize=False, **kwargs):
        """
        Print a JSON string to stdout, with optional highlighting
        """
        if colorize:
            self.stdout.print(self.highlight_json(data, **kwargs))
        else:
            self.print_raw_line(self.orjson.dumps(data))

    def print_raw_line(self, line):
        """
        Write a line of raw bytes to stdout
        """
        self.sys.stdout.buffer.write(line + b"\n")

    def timestamp_to_human(self, *args, **kwargs):
        return timestamp_to_human(*args, **kwargs)

    def seconds_to_human(self, *args, **kwargs):
        return seconds_to_human(*args, **kwargs)
