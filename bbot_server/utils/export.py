import io
import csv
import orjson
from typing import AsyncIterator, Dict


import logging

logger = logging.getLogger(__name__)


async def stream_csv(fieldnames: list[str], rows: AsyncIterator[Dict[str, str]]) -> AsyncIterator[str]:
    """
    Asynchronously stream CSV data line by line.

    Args:
        fieldnames (list[str]): Header fields for the CSV.
        rows (AsyncIterator[Dict[str, str]]): Asynchronous iterator of row data.

    Yields:
        str: CSV lines as strings.

    Example:
        async for line in stream_csv(['name', 'age'], async_row_iterator):
            print(line)
    """
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")

    # Write the header
    writer.writeheader()
    yield output.getvalue()
    output.seek(0)
    output.truncate(0)

    # Write each row
    async for row in rows:
        # pop out custom fields
        row.update(row.pop("fields", {}))
        formatted_row = {}
        for k, v in row.items():
            if isinstance(v, (dict, list, tuple, set)):
                formatted_row[k] = orjson.dumps(v).decode()
            else:
                formatted_row[k] = str(v)
        writer.writerow(formatted_row)
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)
