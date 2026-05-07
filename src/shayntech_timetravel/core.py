"""Shayntech TimeTravel — Immutable change tracking and hash chain."""

import json
import hashlib
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Optional


class HashChain:
    """Immutable hash chain for change verification.
    
    Each change is hashed with the previous change's hash to form
    a tamper-evident chain. Like a blockchain, but simple.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_history_table()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_history_table(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS _tt_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                row_id TEXT,
                operation TEXT NOT NULL CHECK(operation IN ('INSERT', 'UPDATE', 'DELETE', 'BASELINE')),
                old_data TEXT,
                new_data TEXT,
                checksum TEXT NOT NULL,
                prev_checksum TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tt_table ON _tt_history(table_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tt_time ON _tt_history(created_at)")
        conn.commit()
        conn.close()

    def get_last_checksum(self) -> Optional[str]:
        conn = self._get_conn()
        row = conn.execute("SELECT checksum FROM _tt_history ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        return row["checksum"] if row else None

    def compute_hash(self, entry: dict) -> str:
        """Compute SHA-256 hash of a change entry."""
        raw = json.dumps(entry, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def record(self, table: str, row_id: str, operation: str, 
               old_data: dict, new_data: dict) -> dict:
        """Record a change and return the entry."""
        prev = self.get_last_checksum()
        
        entry = {
            "table": table,
            "row_id": str(row_id),
            "operation": operation,
            "old_data": old_data,
            "new_data": new_data,
            "prev_checksum": prev or "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        checksum = self.compute_hash(entry)
        entry["checksum"] = checksum
        
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO _tt_history 
               (table_name, row_id, operation, old_data, new_data, checksum, prev_checksum, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (table, row_id, operation, 
             json.dumps(old_data) if old_data else None,
             json.dumps(new_data) if new_data else None,
             checksum, prev, entry["timestamp"])
        )
        conn.commit()
        conn.close()
        return entry

    def verify_chain(self) -> dict:
        """Verify the entire hash chain integrity."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id, table_name, row_id, operation, old_data, new_data, checksum, prev_checksum, created_at "
            "FROM _tt_history ORDER BY id"
        ).fetchall()
        conn.close()

        if not rows:
            return {"status": "PASS", "message": "No history to verify", "total": 0}

        failures = []
        prev_checksum = None
        for row in rows:
            entry = {
                "table": row["table_name"],
                "row_id": row["row_id"],
                "operation": row["operation"],
                "old_data": json.loads(row["old_data"]) if row["old_data"] else {},
                "new_data": json.loads(row["new_data"]) if row["new_data"] else {},
                "prev_checksum": row["prev_checksum"] or "",
                "timestamp": row["created_at"] or "",
            }
            expected_hash = hashlib.sha256(
                json.dumps(entry, sort_keys=True).encode()
            ).hexdigest()

            if expected_hash != row["checksum"]:
                failures.append({
                    "id": row["id"],
                    "expected": expected_hash,
                    "actual": row["checksum"],
                    "issue": "checksum_mismatch"
                })

            if prev_checksum and row["prev_checksum"] != prev_checksum:
                failures.append({
                    "id": row["id"],
                    "expected_prev": prev_checksum,
                    "actual_prev": row["prev_checksum"],
                    "issue": "chain_break"
                })
            prev_checksum = row["checksum"]

        return {
            "status": "FAIL" if failures else "PASS",
            "total": len(rows),
            "failures": len(failures),
            "details": failures
        }


class TimeTravelDB:
    """Wraps a SQLite database with automatic change tracking."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.chain = HashChain(db_path)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._capture_enabled = True

    def execute(self, sql: str, params: tuple = ()) -> Any:
        """Execute SQL with automatic change capture."""
        sql_upper = sql.strip().upper()
        
        if not self._capture_enabled:
            return self._conn.execute(sql, params)
        
        # For UPDATE/DELETE, capture old data first
        if sql_upper.startswith("UPDATE"):
            self._capture_update(sql, params)
        elif sql_upper.startswith("DELETE"):
            self._capture_delete(sql, params)
        elif sql_upper.startswith("INSERT"):
            pass  # Will capture via rowid after insert
        
        result = self._conn.execute(sql, params)
        
        if sql_upper.startswith("INSERT") and result.lastrowid:
            self._capture_insert(sql, params, result.lastrowid)
        
        self._conn.commit()
        return result

    def _capture_insert(self, sql: str, params: tuple, row_id: int):
        table = self._extract_table(sql)
        # Read back what was inserted
        row = self._conn.execute(f"SELECT rowid AS tt_rid, * FROM \"{table}\" WHERE rowid = ?", (row_id,)).fetchone()
        if row:
            data = dict(row)
            rid = str(data.pop("tt_rid"))
            self.chain.record(table, rid, "INSERT", {}, data)

    def _capture_update(self, sql: str, params: tuple):
        table = self._extract_table(sql)
        # Read current state before update
        where = self._extract_where(sql)
        if where:
            # Simple approach: select matching rows
            select_sql = f"SELECT rowid AS tt_rid, * FROM \"{table}\" WHERE {where}"
            try:
                rows = self._conn.execute(select_sql, params).fetchall()
                for row in rows:
                    row_dict = dict(row)
                    rid = str(row_dict.pop("tt_rid"))
                    self.chain.record(table, rid, "UPDATE", row_dict, {})
            except Exception:
                pass  # best effort capture

    def _capture_delete(self, sql: str, params: tuple):
        table = self._extract_table(sql)
        where = self._extract_where(sql)
        if where:
            select_sql = f"SELECT rowid AS tt_rid, * FROM \"{table}\" WHERE {where}"
            try:
                rows = self._conn.execute(select_sql, params).fetchall()
                for row in rows:
                    row_dict = dict(row)
                    rid = str(row_dict.pop("tt_rid"))
                    self.chain.record(table, rid, "DELETE", row_dict, {})
            except Exception:
                pass

    def _extract_table(self, sql: str) -> str:
        """Extract table name from SQL (simple parser)."""
        parts = sql.split()
        for i, p in enumerate(parts):
            upper = p.upper()
            if upper in ("FROM", "UPDATE", "INTO", "TABLE"):
                if i + 1 < len(parts):
                    return parts[i + 1].strip('"').strip("'").strip("`")
        return "unknown"

    def _extract_where(self, sql: str) -> str:
        """Extract WHERE clause from SQL."""
        idx = sql.upper().find("WHERE")
        if idx >= 0:
            return sql[idx + 6:]
        return ""

    def query_at(self, timestamp: str, table: str, row_id: str = None) -> list[dict]:
        """Query data as it existed at a given timestamp.
        
        Algorithm:
        1. Get current state of the table
        2. Replay changes in reverse chronological order up to target time
        3. For each change: undo the operation to reconstruct past state
        """
        # Get all changes up to the target timestamp, in reverse order
        conn = self.chain._get_conn()
        rows = conn.execute(
            """SELECT * FROM _tt_history 
               WHERE table_name = ? AND created_at > ?
               ORDER BY id DESC""",
            (table, timestamp)
        ).fetchall()
        conn.close()

        # Get current state
        cur = self._conn.execute(f"SELECT rowid AS tt_rid, * FROM \"{table}\"")
        current = {str(r["tt_rid"]): dict(r) for r in cur.fetchall()}

        # Replay changes in reverse (skip BASELINE — they're not changes to undo)
        for change in rows:
            if change["operation"] == "BASELINE":
                continue
            rid = change["row_id"]
            op = change["operation"]
            old = json.loads(change["old_data"]) if change["old_data"] else {}
            new_data = json.loads(change["new_data"]) if change["new_data"] else {}

            if op == "INSERT":
                # Row didn't exist before this insert
                current.pop(rid, None)
            elif op == "UPDATE":
                # Restore old values
                if rid in current:
                    for k, v in old.items():
                        if k in current[rid]:
                            current[rid][k] = v
            elif op == "DELETE":
                # Row existed before delete
                if old:
                    current[rid] = old

        # Filter by row_id if specified
        if row_id:
            return [current[row_id]] if row_id in current else []
        
        return list(current.values())

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
