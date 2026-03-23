"""DuckDB connection management for FastAPI."""

import threading

import duckdb

from config import DB_PATH

_local = threading.local()


def get_connection() -> duckdb.DuckDBPyConnection:
    """Return a thread-local read-only DuckDB connection.

    DuckDB supports multiple readers but only one writer.
    For the API layer we only need reads.
    """
    if not hasattr(_local, "con") or _local.con is None:
        _local.con = duckdb.connect(str(DB_PATH), read_only=True)
    return _local.con
