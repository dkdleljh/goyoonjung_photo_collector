from __future__ import annotations

import sqlite3
from pathlib import Path


class DedupStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS hashes (
                sha256 TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def has(self, sha256_hex: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM hashes WHERE sha256 = ?", (sha256_hex,)).fetchone()
        return row is not None

    def add(self, sha256_hex: str, created_at: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO hashes (sha256, created_at) VALUES (?, ?)",
            (sha256_hex, created_at),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
