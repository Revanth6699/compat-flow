"""Bounded primitives shared by file and connector ingestion.

The helpers deliberately keep only one batch in Python memory. Duplicate keys
are persisted in a temporary SQLite database so duplicates are detected across
batch boundaries without retaining the complete key set in RAM.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence, TypeVar

T = TypeVar("T")


class BatchConfigurationError(ValueError):
    """Raised when a batch-processing configuration is unsafe."""


def iter_batches(items: Iterable[T], batch_size: int = 500) -> Iterator[list[T]]:
    """Yield fixed-size lists from any iterable without materializing it."""
    if isinstance(batch_size, bool) or batch_size < 1 or batch_size > 10_000:
        raise BatchConfigurationError("batch_size must be between 1 and 10,000.")
    batch: list[T] = []
    for item in items:
        batch.append(item)
        if len(batch) == batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


@dataclass(frozen=True)
class DuplicateMatch:
    duplicate: bool
    first_source_location: str | None = None


class DiskBackedDuplicateTracker:
    """Exact duplicate tracking with bounded Python memory.

    The database is private to this tracker, uses a primary-key uniqueness
    constraint, and is removed when the context manager exits. Keys are
    serialized deterministically; callers should pass normalized domain keys,
    not entire source rows unless whole-row duplication is intended.
    """

    def __init__(self, directory: str | Path | None = None) -> None:
        self._temporary = tempfile.NamedTemporaryFile(
            prefix="compatflow-dedupe-", suffix=".sqlite3",
            dir=str(directory) if directory else None, delete=False,
        )
        self.path = Path(self._temporary.name)
        self._temporary.close()
        self._connection = sqlite3.connect(str(self.path))
        self._connection.execute("PRAGMA journal_mode=OFF")
        self._connection.execute("PRAGMA synchronous=OFF")
        self._connection.execute(
            "CREATE TABLE seen (key TEXT PRIMARY KEY, source_location TEXT NOT NULL)"
        )
        self._closed = False

    @staticmethod
    def _serialize(key: Sequence[Any]) -> str:
        try:
            return json.dumps(list(key), ensure_ascii=False, sort_keys=True,
                              separators=(",", ":"), default=str)
        except (TypeError, ValueError, RecursionError):
            raise BatchConfigurationError("Duplicate key cannot be serialized safely.") from None

    def check_and_add(self, key: Sequence[Any], source_location: str) -> DuplicateMatch:
        if self._closed:
            raise RuntimeError("Duplicate tracker is closed.")
        serialized = self._serialize(key)
        cursor = self._connection.execute(
            "INSERT OR IGNORE INTO seen (key, source_location) VALUES (?, ?)",
            (serialized, str(source_location)[:512]),
        )
        if cursor.rowcount == 1:
            return DuplicateMatch(False)
        row = self._connection.execute(
            "SELECT source_location FROM seen WHERE key = ?", (serialized,)
        ).fetchone()
        return DuplicateMatch(True, row[0] if row else None)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._connection.close()
        finally:
            self.path.unlink(missing_ok=True)

    def __enter__(self) -> "DiskBackedDuplicateTracker":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
