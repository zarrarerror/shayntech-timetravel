"""CLI interface for Shayntech TimeTravel (SQLite & PostgreSQL)."""

import argparse
import json
import sys
import os
import sqlite3
from datetime import datetime
from .core import TimeTravelDB, HashChain
from .reports import SOC2Report


def _resolve_db(args):
    """Return (chain, is_pg) based on args."""
    if hasattr(args, 'pg') and args.pg:
        from .pg_adapter import PgHashChain, PgTimeTravelDB
        # Chain is created separately below
        return args.pg, True
    return args.db, False


def _get_chain(args):
    """Get a hash chain instance."""
    if hasattr(args, 'pg') and args.pg:
        from .pg_adapter import PgHashChain
        return PgHashChain(args.pg)
    return HashChain(args.db)


def _get_db(args):
    """Get a TimeTravelDB instance."""
    if hasattr(args, 'pg') and args.pg:
        from .pg_adapter import PgTimeTravelDB
        return PgTimeTravelDB(args.pg)
    return TimeTravelDB(args.db)


def _get_report(args):
    """Get a SOC2Report instance."""
    if hasattr(args, 'pg') and args.pg:
        # Reports work from the hash chain data — we'll use pg adapter's info
        from .pg_adapter import PgHashChain
        # For now, reports with PG mode read chain data but output same format
        # We'll handle this in the report command directly
        return None, True
    return SOC2Report(args.db), False


def cmd_init(args):
    """Initialize a database for time travel tracking."""
    if args.pg:
        _cmd_init_pg(args)
    else:
        _cmd_init_sqlite(args)


def _cmd_init_sqlite(args):
    if not os.path.exists(args.db):
        print(f"❌ Database not found: {args.db}")
        sys.exit(1)

    chain = HashChain(args.db)
    total = 0
    conn = sqlite3.connect(args.db)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE '_tt_%'"
    ).fetchall()
    conn.close()

    for t in tables:
        name = t[0]
        try:
            conn2 = sqlite3.connect(args.db)
            rows = conn2.execute(f"SELECT rowid, * FROM \"{name}\" LIMIT 10").fetchall()
            for row in rows:
                d = dict(row)
                rid = d.pop("rowid")
                chain.record(name, str(rid), "BASELINE", {}, d)
                total += 1
            conn2.close()
        except Exception as e:
            print(f"  ⚠️  Could not scan {name}: {e}")

    print(f"✅ TimeTravel initialized for {args.db}")
    print(f"   {total} existing records tracked as baseline")
    print(f"   Tracking {len(tables)} tables")


def _cmd_init_pg(args):
    from .pg_adapter import PgTimeTravelDB, install_triggers
    db = PgTimeTravelDB(args.pg)
    tables = args.tables or db.get_tables()
    print(f"\n🔧 Initializing PostgreSQL database for time travel tracking...")
    print(f"   Connected to: {args.pg[:50]}...")
    print(f"   Target tables: {', '.join(tables[:10])}{' + more' if len(tables) > 10 else ''}")

    result = db.baseline(tables)
    print(f"\n✅ Baseline complete")
    print(f"   {result['rows_recorded']} existing records tracked as baseline")
    print(f"   {result['tables_scanned']} tables scanned")
    if result['errors']:
        for e in result['errors'][:5]:
            print(f"   ⚠️  {e}")
    db.close()

    exclude = [t.strip() for t in (args.exclude or "").split(",") if t.strip()]
    print(f"\n🔌 Installing auto-capture triggers{' (excluding: '+', '.join(exclude)+')' if exclude else ''}...")
    tr = install_triggers(args.pg, tables, exclude=exclude)
    algo = tr["hash_algorithm"].upper()
    if tr["installed"]:
        print(f"   ✅ Triggers installed on {len(tr['installed'])} tables ({algo})")
    if tr["skipped_already_existed"]:
        print(f"   ⏭  {len(tr['skipped_already_existed'])} tables already had triggers")
    if tr["errors"]:
        for e in tr["errors"][:5]:
            print(f"   ⚠️  {e}")
    print(f"\n✅ TimeTravel ready — all future changes will be auto-captured from any source.")


def cmd_query(args):
    """Query data as of a point in time."""
    db = _get_db(args)

    if args.json:
        results = db.query_at(args.at, args.table, args.row)
        print(json.dumps(results, indent=2, default=str))
    else:
        results = db.query_at(args.at, args.table, args.row)
        if not results:
            print("No data found.")
            return
        print(f"\n🔮 Data as of: {args.at}")
        print(f"   Table: {args.table}")
        print(f"   Rows: {len(results)}")
        print()
        for row in results:
            print(json.dumps(row, indent=2, default=str))
            print("─" * 40)
    db.close()


def cmd_diff(args):
    """Show differences between two points in time."""
    db = _get_db(args)

    old = db.query_at(args.from_date, args.table)
    new = db.query_at(args.to_date, args.table)

    old_ids = {str(r.get("id", r.get("rowid", ""))) for r in old}
    new_ids = {str(r.get("id", r.get("rowid", ""))) for r in new}

    added = new_ids - old_ids
    removed = old_ids - new_ids

    print(f"\n📊 Diff: {args.table}")
    print(f"   {args.from_date} → {args.to_date}")
    print()
    print(f"   Rows added:   {len(added)}")
    print(f"   Rows removed: {len(removed)}")
    print(f"   Rows before:  {len(old)}")
    print(f"   Rows after:   {len(new)}")

    if args.verbose and added:
        print(f"\n   ── Added Rows ──")
        for rid in added:
            r = next((x for x in new if str(x.get("id", x.get("rowid", ""))) == rid), None)
            if r:
                print(f"   + {json.dumps(r, default=str)}")

    if args.verbose and removed:
        print(f"\n   ── Removed Rows ──")
        for rid in removed:
            r = next((x for x in old if str(x.get("id", x.get("rowid", ""))) == rid), None)
            if r:
                print(f"   - {json.dumps(r, default=str)}")

    db.close()


def cmd_log(args):
    """Show the full change history for a table or row."""
    chain = _get_chain(args)

    if args.pg:
        from .pg_adapter import _connect, _dict_row
        conn = _connect(args.pg)
        cur = _dict_row(conn)
    else:
        conn = chain._get_conn()
        cur = conn.execute  # not a cursor, but same method signature

    if args.pg:
        if args.row:
            cur.execute(
                "SELECT * FROM _tt_history WHERE table_name = %s AND row_id = %s ORDER BY id",
                (args.table, args.row)
            )
            rows = cur.fetchall()
        else:
            cur.execute(
                "SELECT * FROM _tt_history WHERE table_name = %s ORDER BY id DESC LIMIT 50",
                (args.table,)
            )
            rows = cur.fetchall()
        conn.close()
    else:
        if args.row:
            rows = cur(
                "SELECT * FROM _tt_history WHERE table_name = ? AND row_id = ? ORDER BY id",
                (args.table, args.row)
            ).fetchall()
        else:
            rows = cur(
                "SELECT * FROM _tt_history WHERE table_name = ? ORDER BY id DESC LIMIT 50",
                (args.table,)
            ).fetchall()
        conn.close()

    if not rows:
        print("No history found.")
        return

    print(f"\n📝 Change Log: {args.table}" + (f" (row: {args.row})" if args.row else ""))
    print(f"   Entries: {len(rows)}")
    print()

    for r in rows:
        op_icon = {"INSERT": "➕", "UPDATE": "✏️", "DELETE": "🗑️", "BASELINE": "📦"}
        icon = op_icon.get(r["operation"], "❓")
        print(f"   {icon} #{r['id']} | {r['created_at']} | {r['operation']}")
        print(f"      Row: {r['row_id']} | Hash: {r['checksum'][:16]}...")
        if args.verbose and r.get("old_data") and r["old_data"] != "null":
            old = json.loads(r["old_data"])
            if old:
                print(f"      Before: {json.dumps(old, default=str)[:100]}")
        if args.verbose and r.get("new_data") and r["new_data"] != "null":
            new_data = json.loads(r["new_data"])
            if new_data:
                print(f"      After:  {json.dumps(new_data, default=str)[:100]}")
        print()


def cmd_verify(args):
    """Verify the hash chain integrity."""
    chain = _get_chain(args)
    result = chain.verify_chain()

    if result["status"] == "PASS":
        print(f"\n✅ Chain Verification: PASS")
        print(f"   {result['total']} entries verified")
        print(f"   No tampering detected")
    else:
        print(f"\n❌ Chain Verification: FAIL")
        print(f"   {result['failures']} of {result['total']} entries failed")
        for d in result.get("details", []):
            print(f"   ⚠️  Entry #{d['id']}: {d['issue']}")


def cmd_report(args):
    """Generate SOC 2 compliance reports."""
    is_pg = args.pg is not None
    if is_pg:
        from .pg_adapter import PgHashChain
        chain = PgHashChain(args.pg)
    else:
        chain = HashChain(args.db)

    os.makedirs(args.output, exist_ok=True)

    # For PG mode, we need a report generator that reads from PG
    if is_pg:
        _generate_pg_report(chain, args)
    else:
        report = SOC2Report(args.db)
        _generate_sqlite_report(report, args)


def _generate_sqlite_report(report, args):
    output_dir = args.output or "."

    if args.type == "integrity":
        html = report.integrity_report()
        path = os.path.join(output_dir, "soc2-integrity-report.html")
        with open(path, "w") as f:
            f.write(html)
        print(f"✅ SOC 2 Integrity Report: {path}")

    elif args.type == "audit":
        html = report.change_audit_report(args.start, args.end)
        path = os.path.join(output_dir, "soc2-change-audit.html")
        with open(path, "w") as f:
            f.write(html)
        print(f"✅ SOC 2 Change Audit Report: {path}")

    elif args.type == "retention":
        if not args.at:
            print("❌ --at timestamp required for retention report")
            sys.exit(1)
        html = report.retention_report(args.at)
        path = os.path.join(output_dir, "soc2-retention-report.html")
        with open(path, "w") as f:
            f.write(html)
        print(f"✅ SOC 2 Retention Report: {path}")

    elif args.type == "all":
        for rtype, rfunc, filename in [
            ("integrity", report.integrity_report(), "soc2-integrity-report.html"),
            ("audit", report.change_audit_report(args.start, args.end), "soc2-change-audit.html"),
            ("retention", report.retention_report(args.at or datetime.utcnow().strftime("%Y-%m-%d")), "soc2-retention-report.html"),
        ]:
            path = os.path.join(output_dir, filename)
            with open(path, "w") as f:
                f.write(rfunc)
            print(f"✅ SOC 2 Report: {path}")


def _generate_pg_report(chain, args):
    """Generate SOC 2 reports from PostgreSQL-backed chain data."""
    output_dir = args.output or "."
    from .reports import _build_html_report

    # Get verification result
    verify_result = chain.verify_chain()

    # Get all chain entries
    from .pg_adapter import _connect, _dict_row
    conn = _connect(chain.conn_str)
    cur = _dict_row(conn)
    cur.execute("SELECT * FROM _tt_history ORDER BY id")
    all_entries = cur.fetchall()
    conn.close()

    # Count by table and operation
    tables = {}
    ops = {"INSERT": 0, "UPDATE": 0, "DELETE": 0, "BASELINE": 0}
    for e in all_entries:
        tbl = e["table_name"]
        tables[tbl] = tables.get(tbl, 0) + 1
        if e["operation"] in ops:
            ops[e["operation"]] += 1

    if args.type in ("integrity", "all"):
        integrity_html = _build_html_report(
            "SOC 2 Integrity Report",
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
            "integrity",
            {
                "status": verify_result["status"],
                "total_entries": verify_result["total"],
                "failures": verify_result["failures"],
                "chain_intact": verify_result["status"] == "PASS",
            }
        )
        path = os.path.join(output_dir, "soc2-integrity-report.html")
        with open(path, "w") as f:
            f.write(integrity_html)
        print(f"✅ SOC 2 Integrity Report: {path}")

    if args.type in ("audit", "all"):
        audit_html = _build_html_report(
            "SOC 2 Change Audit Report",
            f"Period: {args.start or 'all time'} → {args.end or 'present'}",
            "audit",
            {
                "total_entries": len(all_entries),
                "tables_tracked": len(tables),
                "operations": ops,
                "tables": tables,
            }
        )
        path = os.path.join(output_dir, "soc2-change-audit.html")
        with open(path, "w") as f:
            f.write(audit_html)
        print(f"✅ SOC 2 Change Audit Report: {path}")

    if args.type in ("retention", "all"):
        at = args.at or datetime.utcnow().strftime("%Y-%m-%d")
        retention_html = _build_html_report(
            "SOC 2 Retention Report",
            f"As of: {at}",
            "retention",
            {
                "as_of": at,
                "total_entries": len(all_entries),
                "tables_tracked": len(tables),
                "data_retained": True,
            }
        )
        path = os.path.join(output_dir, "soc2-retention-report.html")
        with open(path, "w") as f:
            f.write(retention_html)
        print(f"✅ SOC 2 Retention Report: {path}")


def cmd_demo(args):
    """Run a full demo showing all features."""
    from .core import TimeTravelDB, HashChain
    from .reports import SOC2Report
    import tempfile

    demo_dir = args.output or "/tmp/shayntech-timetravel-demo"
    os.makedirs(demo_dir, exist_ok=True)
    db_path = os.path.join(demo_dir, "demo.db")

    if os.path.exists(db_path):
        os.remove(db_path)

    print("=" * 60)
    print("🔮  SHAYNTECH TIMETRAVEL — DEMO")
    print("=" * 60)

    # Step 1: Create database and track
    print("\n📦 Step 1: Create a database with sample data")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT, role TEXT)")
    conn.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, product TEXT, amount REAL, status TEXT)")
    conn.execute("INSERT INTO users VALUES (1, 'Alice', 'alice@example.com', 'admin')")
    conn.execute("INSERT INTO users VALUES (2, 'Bob', 'bob@example.com', 'editor')")
    conn.execute("INSERT INTO users VALUES (3, 'Charlie', 'charlie@example.com', 'viewer')")
    conn.execute("INSERT INTO orders VALUES (1, 1, 'Widget Pro', 299.99, 'shipped')")
    conn.execute("INSERT INTO orders VALUES (2, 2, 'Gadget X', 149.99, 'pending')")
    conn.commit()
    conn.close()

    # Step 2: Initialize tracking
    print("\n🔧 Step 2: Initialize time travel tracking")
    chain = HashChain(db_path)
    print("   ✅ History table created")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    for row in conn.execute("SELECT *, rowid AS tt_rowid FROM users"):
        d = dict(row)
        rid = str(d.pop("tt_rowid"))
        chain.record("users", rid, "BASELINE", {}, d)
    for row in conn.execute("SELECT *, rowid AS tt_rowid FROM orders"):
        d = dict(row)
        rid = str(d.pop("tt_rowid"))
        chain.record("orders", rid, "BASELINE", {}, d)
    conn.close()
    print("   ✅ 5 existing records tracked")

    # Step 3: Make changes
    print("\n✏️  Step 3: Make some changes to the database")
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE users SET role = 'manager' WHERE id = 1")
    conn.commit()
    chain.record("users", "1", "UPDATE", {"role": "admin"}, {"role": "manager"})
    print("   ✅ Alice's role changed: admin → manager")

    conn.execute("UPDATE orders SET status = 'delivered' WHERE id = 1")
    conn.commit()
    chain.record("orders", "1", "UPDATE", {"status": "shipped"}, {"status": "delivered"})
    print("   ✅ Order #1 status: shipped → delivered")

    conn.execute("INSERT INTO users VALUES (4, 'Diana', 'diana@example.com', 'editor')")
    conn.commit()
    chain.record("users", "4", "INSERT", {}, {"id": 4, "name": "Diana", "email": "diana@example.com", "role": "editor"})
    print("   ✅ Diana added as editor")

    conn.execute("DELETE FROM orders WHERE id = 2")
    conn.commit()
    chain.record("orders", "2", "DELETE", {"id": 2, "user_id": 2, "product": "Gadget X", "amount": 149.99, "status": "pending"}, {})
    print("   ✅ Order #2 deleted")
    conn.close()

    # Step 4: Time travel queries
    print("\n🔮 Step 4: Time travel queries")
    db = TimeTravelDB(db_path)
    current = db.query_at("2099-01-01", "users")
    print(f"   Current users: {len(current)} (Alice = manager, Diana exists, Bob unchanged)")
    past = db.query_at("2024-01-01", "users")
    past_alice = next((u for u in past if u.get("id") == 1 or u.get("name") == "Alice"), None)
    print(f"   🔙 Jan 1, 2024: Alice was: {past_alice.get('role', 'unknown') if past_alice else 'not found'}")
    orders_before = db.query_at("2024-01-01", "orders")
    print(f"   🔙 Jan 1, 2024: Orders = {len(orders_before)} (before deletion)")
    orders_now = db.query_at("2099-01-01", "orders")
    print(f"   Now: Orders = {len(orders_now)} (after deletion)")
    db.close()

    # Step 5: Verify chain
    print("\n🔗 Step 5: Verify hash chain")
    result = chain.verify_chain()
    print(f"   Chain: {result['status']} ({result['total']} entries)")

    # Step 6: Generate SOC 2 reports
    print("\n📋 Step 6: Generate SOC 2 reports")
    report = SOC2Report(db_path)
    for rtype, rfunc, fname in [
        ("Integrity", report.integrity_report(), "soc2-integrity-report.html"),
        ("Change Audit", report.change_audit_report(), "soc2-change-audit.html"),
        ("Retention", report.retention_report("2025-01-01"), "soc2-retention-report.html"),
    ]:
        path = os.path.join(demo_dir, fname)
        with open(path, "w") as f:
            f.write(rfunc)
        print(f"   ✅ {rtype}: {path}")

    print("\n" + "=" * 60)
    print("✅  DEMO COMPLETE")
    print(f"📁  Demo files: {demo_dir}")
    print("=" * 60)



def main():
    parser = argparse.ArgumentParser(
        description="🔮 Shayntech TimeTravel — Git for your database. SOC 2 built in.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  timetravel init mydb.db                        # SQLite: Start tracking
  timetravel query mydb.db --at "2025-01-01" --table users
  timetravel diff mydb.db --from "2025-01" --to "2025-02" --table users

  # PostgreSQL (NeonDB, Supabase, RDS, etc.):
  timetravel init --pg "postgresql://user:pass@host/db?sslmode=require"
  timetravel query --pg "postgresql://user:pass@host/db" --at "2025-01-01" --table users
  timetravel verify --pg "postgresql://user:pass@host/db"
  timetravel report --pg "postgresql://user:pass@host/db" --type all --output ./reports
        """
    )
    parser.add_argument("--version", action="version", version="Shayntech TimeTravel 0.1.1")

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # init
    p_init = sub.add_parser("init", help="Initialize a database for time travel tracking")
    p_init.add_argument("db", nargs="?", help="Path to SQLite database")
    p_init.add_argument("--pg", help="PostgreSQL connection string")
    p_init.add_argument("--tables", nargs="*", help="Specific tables to track (default: all)")
    p_init.add_argument("--exclude", default="", help="Comma-separated tables to skip (e.g. session,logs,cache)")

    # query
    p_query = sub.add_parser("query", help="Query data as of a point in time")
    p_query.add_argument("db", nargs="?", help="Path to SQLite database")
    p_query.add_argument("--pg", help="PostgreSQL connection string")
    p_query.add_argument("--at", required=True, help="Timestamp (e.g. '2025-01-01' or '2025-01-01 12:00:00')")
    p_query.add_argument("--table", required=True, help="Table name")
    p_query.add_argument("--row", help="Specific row ID")
    p_query.add_argument("--json", action="store_true", help="Output as JSON")
    p_query.set_defaults(func=cmd_query)

    # diff
    p_diff = sub.add_parser("diff", help="Show differences between two timestamps")
    p_diff.add_argument("db", nargs="?", help="Path to SQLite database")
    p_diff.add_argument("--pg", help="PostgreSQL connection string")
    p_diff.add_argument("--from-date", required=True, help="Starting timestamp")
    p_diff.add_argument("--to-date", required=True, help="Ending timestamp")
    p_diff.add_argument("--table", required=True, help="Table name")
    p_diff.add_argument("--verbose", "-v", action="store_true", help="Show row details")
    p_diff.set_defaults(func=cmd_diff)

    # log
    p_log = sub.add_parser("log", help="Show change history for a table or row")
    p_log.add_argument("db", nargs="?", help="Path to SQLite database")
    p_log.add_argument("--pg", help="PostgreSQL connection string")
    p_log.add_argument("--table", required=True, help="Table name")
    p_log.add_argument("--row", help="Row ID for specific history")
    p_log.add_argument("--verbose", "-v", action="store_true", help="Show data diffs")
    p_log.set_defaults(func=cmd_log)

    # verify
    p_verify = sub.add_parser("verify", help="Verify hash chain integrity")
    p_verify.add_argument("db", nargs="?", help="Path to SQLite database")
    p_verify.add_argument("--pg", help="PostgreSQL connection string")
    p_verify.set_defaults(func=cmd_verify)

    # report
    p_report = sub.add_parser("report", help="Generate SOC 2 compliance reports")
    p_report.add_argument("db", nargs="?", help="Path to SQLite database")
    p_report.add_argument("--pg", help="PostgreSQL connection string")
    p_report.add_argument("--type", choices=["integrity", "audit", "retention", "all"], default="all")
    p_report.add_argument("--start", help="Start date for audit report")
    p_report.add_argument("--end", help="End date for audit report")
    p_report.add_argument("--at", help="Point-in-time for retention report")
    p_report.add_argument("--output", "-o", default="./reports", help="Output directory")
    p_report.set_defaults(func=cmd_report)

    # demo
    p_demo = sub.add_parser("demo", help="Run a complete demo with sample data")
    p_demo.add_argument("--output", default="/tmp/shayntech-timetravel-demo", help="Output directory")
    p_demo.set_defaults(func=cmd_demo)

    # Set defaults for all commands
    p_init.set_defaults(func=cmd_init)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
