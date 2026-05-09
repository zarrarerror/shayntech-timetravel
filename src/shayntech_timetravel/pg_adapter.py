"""PostgreSQL adapter for Shayntech TimeTravel.

Supports any PostgreSQL-compatible database (NeonDB, Supabase, RDS, etc.).
Mirrors the SQLite API so all commands work identically.
"""

import json
import hashlib
from datetime import datetime, timezone
from typing import Any, Optional

try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


def _connect(conn_str: str):
    """Create a PostgreSQL connection."""
    if not HAS_PSYCOPG2:
        raise ImportError(
            "psycopg2 is required for PostgreSQL support.\n"
            "Install: pip install psycopg2-binary"
        )
    conn = psycopg2.connect(conn_str)
    conn.autocommit = False
    return conn


def _dict_row(conn):
    """Return a dict-like cursor factory."""
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def install_triggers(conn_str: str, tables: list = None, exclude: list = None) -> dict:
    """Install PostgreSQL triggers so every INSERT/UPDATE/DELETE is auto-captured.

    Creates a single shared trigger function _tt_trigger_capture() plus one
    AFTER trigger per table.  Safe to call repeatedly — skips tables that
    already have the trigger installed.
    """
    conn = _connect(conn_str)
    cur = conn.cursor()

    # Try to enable pgcrypto for SHA-256; fall back to MD5 if unavailable
    has_pgcrypto = False
    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        conn.commit()
        cur.execute("SELECT encode(digest('x','sha256'),'hex')")
        cur.fetchone()
        has_pgcrypto = True
    except Exception:
        conn.rollback()

    hash_expr = (
        "encode(digest(data_str,'sha256'),'hex')"
        if has_pgcrypto else
        "md5(data_str)"
    )

    # Single shared trigger function — PK column is passed as trigger argument
    cur.execute(f"""
        CREATE OR REPLACE FUNCTION _tt_trigger_capture()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        DECLARE
          pk_col     TEXT := TG_ARGV[0];
          row_id_val TEXT;
          old_json   TEXT;
          new_json   TEXT;
          ts         TEXT;
          prev_hash  TEXT;
          data_str   TEXT;
          csum       TEXT;
        BEGIN
          ts := to_char(NOW() AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS+00:00');
          IF TG_OP = 'DELETE' THEN
            row_id_val := (row_to_json(OLD)->>pk_col);
            old_json   := row_to_json(OLD)::TEXT;
            new_json   := NULL;
          ELSIF TG_OP = 'INSERT' THEN
            row_id_val := (row_to_json(NEW)->>pk_col);
            old_json   := NULL;
            new_json   := row_to_json(NEW)::TEXT;
          ELSE
            row_id_val := (row_to_json(NEW)->>pk_col);
            old_json   := row_to_json(OLD)::TEXT;
            new_json   := row_to_json(NEW)::TEXT;
          END IF;

          SELECT checksum INTO prev_hash FROM _tt_history ORDER BY id DESC LIMIT 1;

          data_str := TG_TABLE_NAME || '|' ||
                      COALESCE(row_id_val,'') || '|' ||
                      TG_OP || '|' ||
                      COALESCE(old_json,'') || '|' ||
                      COALESCE(new_json,'') || '|' || ts;
          csum := {hash_expr};

          INSERT INTO _tt_history
            (table_name, row_id, operation, old_data, new_data, checksum, prev_checksum, created_at)
          VALUES
            (TG_TABLE_NAME, row_id_val, TG_OP,
             old_json, new_json, csum,
             'TRIGGER:' || COALESCE(prev_hash,''), ts);

          IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
          RETURN NEW;
        END;
        $$
    """)
    conn.commit()

    # Discover tables if not specified
    if tables is None:
        dict_cur = _dict_row(conn)
        dict_cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_type='BASE TABLE' "
            "AND table_name NOT LIKE '\\_tt\\_%' ORDER BY table_name"
        )
        tables = [r["table_name"] for r in dict_cur.fetchall()]

    # Remove excluded tables
    if exclude:
        tables = [t for t in tables if t not in exclude]

    # Find which tables already have the trigger
    cur.execute("SELECT tgname FROM pg_trigger WHERE tgname LIKE '_tt_auto_%'")
    existing = {r[0] for r in cur.fetchall()}

    installed, skipped, errors = [], [], []

    for table in tables:
        trigger_name = f"_tt_auto_{table}"
        if trigger_name in existing:
            skipped.append(table)
            continue
        try:
            # Resolve PK column
            dict_cur = _dict_row(conn)
            dict_cur.execute("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema   = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_name      = %s
                  AND tc.table_schema    = 'public'
                ORDER BY kcu.ordinal_position LIMIT 1
            """, (table,))
            pk_row = dict_cur.fetchone()
            pk_col = pk_row["column_name"] if pk_row else "id"

            cur.execute(f"""
                CREATE TRIGGER {trigger_name}
                AFTER INSERT OR UPDATE OR DELETE ON "{table}"
                FOR EACH ROW EXECUTE FUNCTION _tt_trigger_capture('{pk_col}')
            """)
            conn.commit()
            installed.append(table)
        except Exception as exc:
            conn.rollback()
            errors.append(f"{table}: {exc}")

    conn.close()
    return {
        "installed": installed,
        "skipped_already_existed": skipped,
        "errors": errors,
        "hash_algorithm": "sha256" if has_pgcrypto else "md5",
    }


def _ensure_history_table(conn):
    """Create the _tt_history table in PostgreSQL."""
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS _tt_history (
            id SERIAL PRIMARY KEY,
            table_name TEXT NOT NULL,
            row_id TEXT,
            operation TEXT NOT NULL CHECK(operation IN ('INSERT', 'UPDATE', 'DELETE', 'BASELINE')),
            old_data TEXT,
            new_data TEXT,
            checksum TEXT NOT NULL,
            prev_checksum TEXT,
            created_at TEXT NOT NULL DEFAULT (to_char(now(), 'YYYY-MM-DD HH24:MI:SS'))
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tt_table ON _tt_history(table_name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tt_time ON _tt_history(created_at)")
    conn.commit()
    cur.close()


class PgHashChain:
    """Immutable hash chain stored in a PostgreSQL database."""

    def __init__(self, conn_str: str):
        self.conn_str = conn_str
        conn = _connect(conn_str)
        _ensure_history_table(conn)
        conn.close()

    def _get_cursor(self):
        conn = _connect(self.conn_str)
        cur = _dict_row(conn)
        return conn, cur

    def get_last_checksum(self) -> Optional[str]:
        conn, cur = self._get_cursor()
        cur.execute("SELECT checksum FROM _tt_history ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
        return row["checksum"] if row else None

    def compute_hash(self, entry: dict) -> str:
        raw = json.dumps(entry, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def record(self, table: str, row_id: str, operation: str,
               old_data: dict, new_data: dict) -> dict:
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

        conn, cur = self._get_cursor()
        cur.execute(
            """INSERT INTO _tt_history
               (table_name, row_id, operation, old_data, new_data, checksum, prev_checksum, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (table, row_id, operation,
             json.dumps(old_data, default=str) if old_data else None,
             json.dumps(new_data, default=str) if new_data else None,
             checksum, prev, entry["timestamp"])
        )
        conn.commit()
        conn.close()
        return entry

    def verify_chain(self) -> dict:
        conn, cur = self._get_cursor()
        cur.execute(
            "SELECT id, table_name, row_id, operation, old_data, new_data, checksum, prev_checksum, created_at "
            "FROM _tt_history ORDER BY id"
        )
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return {"status": "PASS", "message": "No history to verify", "total": 0, "failures": 0}

        failures = []
        prev_checksum = None
        trigger_count = 0
        api_count = 0

        for row in rows:
            pc = row["prev_checksum"] or ""
            is_trigger = pc.startswith("TRIGGER:")

            if is_trigger:
                trigger_count += 1
                # Verify the trigger entry's own row hash
                data_str = "|".join([
                    str(row["table_name"]),
                    str(row["row_id"] or ""),
                    str(row["operation"]),
                    str(row["old_data"] or ""),
                    str(row["new_data"] or ""),
                    str(row["created_at"] or ""),
                ])
                stored = str(row["checksum"])
                if len(stored) == 64:
                    expected = hashlib.sha256(data_str.encode()).hexdigest()
                else:
                    import hashlib as _hl2
                    expected = _hl2.md5(data_str.encode()).hexdigest()
                if expected != stored:
                    failures.append({
                        "id": row["id"],
                        "expected": expected,
                        "actual": stored,
                        "issue": "trigger_row_tampered"
                    })
                prev_checksum = stored
            else:
                api_count += 1
                entry = {
                    "table": row["table_name"],
                    "row_id": row["row_id"],
                    "operation": row["operation"],
                    "old_data": json.loads(row["old_data"]) if row["old_data"] else {},
                    "new_data": json.loads(row["new_data"]) if row["new_data"] else {},
                    "prev_checksum": pc,
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
                if prev_checksum and pc != prev_checksum:
                    failures.append({
                        "id": row["id"],
                        "expected_prev": prev_checksum,
                        "actual_prev": pc,
                        "issue": "chain_break"
                    })
                prev_checksum = row["checksum"]

        return {
            "status": "FAIL" if failures else "PASS",
            "total": len(rows),
            "failures": len(failures),
            "api_entries": api_count,
            "trigger_entries": trigger_count,
            "details": failures,
        }


class PgTimeTravelDB:
    """Wraps a PostgreSQL database with time travel tracking.

    Records all data changes in the _tt_history hash chain.
    """

    def __init__(self, conn_str: str):
        self.conn_str = conn_str
        self.chain = PgHashChain(conn_str)

    def get_tables(self) -> list[str]:
        """List user tables in the public schema."""
        conn, cur = self._get_cursor()
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
            "AND table_name NOT LIKE '\\_tt\\_%' "
            "ORDER BY table_name"
        )
        tables = [r["table_name"] for r in cur.fetchall()]
        conn.close()
        return tables

    def get_row_count(self, table: str) -> int:
        conn, cur = self._get_cursor()
        cur.execute(f'SELECT COUNT(*) AS cnt FROM "{table}"')
        row = cur.fetchone()
        conn.close()
        return row["cnt"] if row else 0

    def get_sample_rows(self, table: str, limit: int = 10) -> list[dict]:
        """Get a sample of rows from a table (for baselining)."""
        conn, cur = self._get_cursor()
        try:
            cur.execute(f'SELECT * FROM "{table}" LIMIT %s', (limit,))
            rows = [dict(r) for r in cur.fetchall()]
        except Exception as e:
            rows = []
        conn.close()
        return rows

    def get_row_by_primary_key(self, table: str, pk_col: str, pk_val: Any) -> Optional[dict]:
        """Fetch a single row by its primary key."""
        conn, cur = self._get_cursor()
        try:
            cur.execute(f'SELECT * FROM "{table}" WHERE "{pk_col}" = %s', (pk_val,))
            row = cur.fetchone()
            result = dict(row) if row else None
        except Exception:
            result = None
        conn.close()
        return result

    def get_primary_key_column(self, table: str) -> Optional[str]:
        """Find the primary key column for a table."""
        conn, cur = self._get_cursor()
        cur.execute("""
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
                AND tc.table_name = %s
                AND tc.table_schema = 'public'
            ORDER BY kcu.ordinal_position
            LIMIT 1
        """, (table,))
        row = cur.fetchone()
        conn.close()
        return row["column_name"] if row else "id"

    def baseline(self, tables: list[str] = None) -> dict:
        """Record current state of all (or specified) tables as BASELINE."""
        target_tables = tables or self.get_tables()
        results = {"tables_scanned": 0, "rows_recorded": 0, "errors": []}

        for table in target_tables:
            try:
                pk_col = self.get_primary_key_column(table)
                rows = self.get_sample_rows(table, limit=500)
                for row in rows:
                    pk_val = str(row.get(pk_col, ""))
                    # Remove the entry from data for hash purposes
                    self.chain.record(table, pk_val, "BASELINE", {}, row)
                    results["rows_recorded"] += 1
                results["tables_scanned"] += 1
            except Exception as e:
                results["errors"].append(f"{table}: {e}")

        return results

    def record_update(self, table: str, pk_col: str, pk_val: Any,
                      old_data: dict, new_data: dict) -> dict:
        """Record an UPDATE capturing both before and after state."""
        return self.chain.record(table, str(pk_val), "UPDATE", old_data, new_data)

    def query_at(self, timestamp: str, table: str, row_id: str = None) -> list[dict]:
        """Query data as it existed at a given timestamp.

        Replays changes in reverse chronological order to reconstruct past state.
        """
        conn, cur = self._get_cursor()
        cur.execute(
            "SELECT * FROM _tt_history "
            "WHERE table_name = %s AND created_at > %s "
            "ORDER BY id DESC",
            (table, timestamp)
        )
        changes = cur.fetchall()
        conn.close()

        # Get current state
        conn2, cur2 = self._get_cursor()
        pk_col = self._get_pk(table)
        try:
            cur2.execute(f'SELECT * FROM "{table}"')
            current = {}
            for r in cur2.fetchall():
                d = json.loads(json.dumps(dict(r), default=str))
                rid = str(d.get(pk_col, ""))
                if rid:
                    current[rid] = d
        except Exception:
            current = {}
        conn2.close()

        # Replay changes in reverse to reconstruct past state
        for change in changes:
            if change["operation"] == "BASELINE":
                continue
            rid = change["row_id"]
            op = change["operation"]
            old = json.loads(change["old_data"]) if change["old_data"] else {}
            new_data = json.loads(change["new_data"]) if change["new_data"] else {}

            if op == "INSERT":
                current.pop(rid, None)
            elif op == "UPDATE":
                if rid in current:
                    for k, v in old.items():
                        if k in current[rid]:
                            current[rid][k] = v
            elif op == "DELETE":
                if old:
                    current[rid] = old

        if row_id:
            return [current[row_id]] if row_id in current else []

        return list(current.values())

    def _get_pk(self, table: str) -> str:
        """Get primary key for a table, cached per table."""
        return self.get_primary_key_column(table)

    def _get_cursor(self):
        conn = _connect(self.conn_str)
        cur = _dict_row(conn)
        return conn, cur

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
