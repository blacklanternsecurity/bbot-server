import sqlite3
from typing import Union
from pathlib import Path

from bbot_io.models import *
from bbot_io.config import get_home_dir
from bbot_io.modules.base import BaseIO


class sqlite(BaseIO):

    def __init__(self, db_file: Union[str, Path] = None, table_name: str = "events"):
        if db_file is None:
            db_file = get_home_dir() / "bbot.sqlite"
        self.db_file = Path(db_file)
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        self.table_name = table_name
        self.connection = sqlite3.connect(self.db_file)
        self.connection.row_factory = sqlite3.Row
        self.create_table()

    def create_table(self):
        query = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            rowid INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            id TEXT,
            scope_description TEXT,
            data TEXT,
            host TEXT,
            resolved_hosts TEXT,
            dns_children TEXT,
            web_spider_distance INTEGER,
            scope_distance INTEGER,
            scan TEXT,
            timestamp FLOAT,
            parent TEXT,
            tags TEXT,
            module TEXT,
            module_sequence TEXT,
            discovery_context TEXT
        );
        """
        self.connection.execute(query)
        for field_name in ("type", "id", "host", "scan", "timestamp", "parent"):
            # Create index on the timestamp field
            self.connection.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_{field_name} ON {self.table_name} ({field_name});
            """
            )
        self.connection.commit()

    async def insert_event(self, event: Event):
        query = f"""
        INSERT INTO {self.table_name} (type, id, scope_description, data, host, resolved_hosts, dns_children, web_spider_distance, scope_distance, scan, timestamp, parent, tags, module, module_sequence, discovery_context)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        row = self.event_to_row(event)
        self.connection.execute(query, row)
        self.connection.commit()

    async def get_scans(self, limit: int = None):
        query = (
            f"SELECT * FROM {self.table_name} WHERE type = 'SCAN' LIMIT ?;"
            if limit
            else f"SELECT * FROM {self.table_name} WHERE type = 'SCAN';"
        )
        cursor = self.connection.execute(query, (limit,) if limit else ())
        return cursor.fetchall()

    async def get_subdomains(self):
        query = f"SELECT DISTINCT host FROM {self.table_name} WHERE type = 'DNS_NAME';"
        cursor = self.connection.execute(query)
        return [row[0] for row in cursor.fetchall()]

    async def get_events(self, limit: int = None):
        query = f"SELECT * FROM {self.table_name}"
        if limit:
            query += f" LIMIT {limit}"
        query += " ORDER BY timestamp;"
        cursor = self.connection.execute(query, (limit,) if limit else ())
        rows = cursor.fetchall()
        return [self.event_from_row(row) for row in rows]

    def event_from_row(self, row):
        event_dict = {key: row[key] for key in row.keys() if key != "rowid"}
        return Event.from_flattened(event_dict)

    def event_to_row(self, event):
        event_dict = event.flatten()
        row = (
            event_dict.get("type", ""),
            event_dict.get("id", ""),
            event_dict.get("scope_description", ""),
            event_dict.get("data", '""'),
            event_dict.get("host", None),
            event_dict.get("resolved_hosts", "[]"),
            event_dict.get("dns_children", "{}"),
            event_dict.get("web_spider_distance", 10),
            event_dict.get("scope_distance", 10),
            event_dict.get("scan", ""),
            event_dict.get("timestamp"),
            event_dict.get("parent", ""),
            event_dict.get("tags", "[]"),
            event_dict.get("module", ""),
            event_dict.get("module_sequence", ""),
            event_dict.get("discovery_context", ""),
        )
        return row

    async def drop_database(self):
        query = f"DELETE FROM {self.table_name};"
        self.connection.execute(query)
        self.connection.commit()
