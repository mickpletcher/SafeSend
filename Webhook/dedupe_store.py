"""
Persistent dedupe store for webhook payload fingerprints.
"""

from __future__ import annotations

import asyncio
import sqlite3
import time
from pathlib import Path


class SQLiteDedupeStore:
    def __init__(self, db_path: str, ttl_seconds: int):
        self._db_path = Path(db_path)
        self._ttl_seconds = ttl_seconds
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._init_db)

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dedupe_keys (
                    key TEXT PRIMARY KEY,
                    seen_at INTEGER NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_seen_at ON dedupe_keys (seen_at)")
            conn.commit()

    async def close(self) -> None:
        return None

    async def was_seen(self, key: str) -> bool:
        now = int(time.time())
        cutoff = now - self._ttl_seconds

        async with self._lock:
            return await asyncio.to_thread(self._was_seen_sync, key, now, cutoff)

    def _was_seen_sync(self, key: str, now: int, cutoff: int) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM dedupe_keys WHERE seen_at < ?", (cutoff,))
            existing = conn.execute("SELECT key FROM dedupe_keys WHERE key = ?", (key,)).fetchone()
            if existing:
                return True

            conn.execute(
                "INSERT INTO dedupe_keys (key, seen_at) VALUES (?, ?)",
                (key, now),
            )
            conn.commit()
            return False
