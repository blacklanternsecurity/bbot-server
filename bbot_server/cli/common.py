import io
import typer
import orjson
import logging
import csv as csvlib
from pydantic import BaseModel
from typing import Any, Iterator, Union, Annotated

log = logging.getLogger("bbot_server.cli.common")


def pretty_format(data: Any) -> str:
    if isinstance(data, (dict, list)):
        return orjson.dumps(data).decode()
    return str(data)


def json_to_csv(data: Iterator[Union[dict, BaseModel]], fieldnames: list[str]) -> bytes:
    output = io.StringIO()
    writer = csvlib.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")

    def get_and_clear():
        # read and yield the latest bit from the in-memory file
        value = output.getvalue().encode()
        output.truncate(0)
        output.seek(0)
        return value

    # Write and yield header
    writer.writeheader()
    yield get_and_clear()

    for entry in data:
        if isinstance(entry, BaseModel):
            entry = entry.model_dump()
        elif not isinstance(entry, dict):
            raise ValueError(f"Invalid data type: {type(entry)}")
        row = {}
        for field in fieldnames:
            data = entry.get(field, "")
            row[field] = pretty_format(data)
        writer.writerow(row)
        yield get_and_clear()


### COMMON CLI ARGS ###

json = Annotated[bool, typer.Option("--json", "-j", help="Output as raw JSON")]
csv = Annotated[bool, typer.Option("--csv", "-c", help="Output as CSV")]
