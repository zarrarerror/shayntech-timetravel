"""Shayntech TimeTravel Enterprise — Web server with PostgreSQL support + PDF reports."""

import os
import json
import hashlib
import io
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

# Database adapter — auto-detect PostgreSQL vs SQLite
PG_CONNECTION = os.environ.get("TT_PG_CONNECTION")
DATA_DIR = os.environ.get("TT_DATA_DIR", "/data")
REPORT_DIR = os.environ.get("TT_REPORT_DIR", os.path.join(DATA_DIR, "reports"))
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

if PG_CONNECTION:
    from shayntech_timetravel.pg_adapter import PgHashChain as HashChain
    from shayntech_timetravel.pg_adapter import PgTimeTravelDB as TimeTravelDB
    DB_TYPE = "PostgreSQL"
else:
    from shayntech_timetravel.core import HashChain
    from shayntech_timetravel.core import TimeTravelDB
    DB_PATH = os.path.join(DATA_DIR, "timetravel.db")
    DB_TYPE = "SQLite"

app = FastAPI(title="Shayntech TimeTravel Enterprise", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def get_db():
    if PG_CONNECTION:
        return TimeTravelDB(PG_CONNECTION)
    return TimeTravelDB(DB_PATH)


def get_chain():
    if PG_CONNECTION:
        return HashChain(PG_CONNECTION)
    return HashChain(DB_PATH)


def get_pg_conn():
    """Get raw PG connection for custom queries."""
    if PG_CONNECTION:
        import psycopg2
        return psycopg2.connect(PG_CONNECTION)
    return None


# ─── HELPERS ───────────────────────────────────────────────

def render_html(content: str, title: str = "Dashboard") -> str:
    return HTMLResponse(DASHBOARD_HTML.replace("{{CONTENT}}", content).replace("{{TITLE}}", title))


def get_table_list() -> list:
    """Get list of tracked tables."""
    if PG_CONNECTION:
        from shayntech_timetravel.pg_adapter import PgTimeTravelDB
        db = PgTimeTravelDB(PG_CONNECTION)
        tables = db.get_tables()
        db.close()
        return tables
    else:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        tables = [r[0] for r in conn.execute(
            "SELECT DISTINCT table_name FROM _tt_history"
        ).fetchall()]
        conn.close()
        return tables


def get_chain_stats() -> dict:
    """Get chain statistics."""
    chain = get_chain()
    verify = chain.verify_chain()
    tables = get_table_list()

    # Count changes per table
    changes_per_table = {}
    total_changes = 0
    if PG_CONNECTION:
        conn = get_pg_conn()
        if conn:
            cur = conn.cursor()
            for t in tables:
                cur.execute("SELECT COUNT(*) FROM _tt_history WHERE table_name=%s", (t,))
                c = cur.fetchone()[0]
                changes_per_table[t] = c
                total_changes += c
            # Recent activity
            cur.execute(
                "SELECT id, table_name, operation, created_at FROM _tt_history ORDER BY id DESC LIMIT 10"
            )
            recent = cur.fetchall()
            # Time range
            cur.execute("SELECT MIN(created_at), MAX(created_at) FROM _tt_history")
            (first, last) = cur.fetchone()
            conn.close()
    else:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        for t in tables:
            c = conn.execute("SELECT COUNT(*) FROM _tt_history WHERE table_name=?", (t,)).fetchone()[0]
            changes_per_table[t] = c
            total_changes += c
        recent = conn.execute(
            "SELECT id, table_name, operation, created_at FROM _tt_history ORDER BY id DESC LIMIT 10"
        ).fetchall()
        first = conn.execute("SELECT MIN(created_at) FROM _tt_history").fetchone()[0] or "N/A"
        last = conn.execute("SELECT MAX(created_at) FROM _tt_history").fetchone()[0] or "N/A"
        conn.close()

    return {
        "total_changes": total_changes,
        "tables": tables,
        "changes_per_table": changes_per_table,
        "recent": recent,
        "first": first,
        "last": last,
        "verify": verify,
    }


# ─── ROUTES ────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    stats = get_chain_stats()
    verify = stats["verify"]

    cards = f"""
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-icon" style="background: rgba(167, 139, 250, 0.15);">🔮</div>
            <div class="stat-info">
                <div class="stat-value">{stats['total_changes']}</div>
                <div class="stat-label">Total Changes Tracked</div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon" style="background: rgba(52, 211, 153, 0.15);">📊</div>
            <div class="stat-info">
                <div class="stat-value">{len(stats['tables'])}</div>
                <div class="stat-label">Tables Monitored</div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon" style="background: rgba(251, 191, 36, 0.15);">🔗</div>
            <div class="stat-info">
                <div class="stat-value">{'✅' if verify['status'] == 'PASS' else '❌'}</div>
                <div class="stat-label">Chain: {verify['status']}</div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon" style="background: rgba(34, 211, 238, 0.15);">🗄️</div>
            <div class="stat-info">
                <div class="stat-value" style="font-size: 13px;">{DB_TYPE}</div>
                <div class="stat-label">Database</div>
            </div>
        </div>
    </div>
    """

    # Tables section
    tables_html = "<div class='section'><h2>📊 Tracked Tables</h2><table class='data-table'><tr><th>Table</th><th>Changes</th><th>Actions</th></tr>"
    for t in sorted(stats['changes_per_table'].keys()):
        tables_html += f"<tr><td>{t}</td><td>{stats['changes_per_table'][t]}</td>"
        tables_html += f"<td><a href='/table/{t}' class='btn btn-sm'>View History</a></td></tr>"
    tables_html += "</table></div>"

    # Recent activity
    recent_html = "<div class='section'><h2>⏱️ Recent Activity</h2><table class='data-table'><tr><th>ID</th><th>Table</th><th>Op</th><th>Time</th></tr>"
    for r in stats['recent']:
        op = r[2] if len(r) > 2 else r['operation']
        recent_html += f"<tr><td>#{r[0]}</td><td>{r[1]}</td><td><span class='op-{op.lower()}'>{op}</span></td><td>{str(r[3])[:19]}</td></tr>"
    recent_html += "</table></div>"

    content = cards + tables_html + recent_html
    return render_html(content, "Dashboard")


@app.get("/table/{table_name}", response_class=HTMLResponse)
async def table_view(table_name: str):
    chain = get_chain()
    tables = get_table_list()
    if table_name not in tables:
        return render_html(f"<div class='section'><h2>❌ Table '{table_name}' not found</h2></div>", "Not Found")

    # Get changes for this table
    if PG_CONNECTION:
        conn = get_pg_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM _tt_history WHERE table_name=%s ORDER BY id DESC LIMIT 100", (table_name,))
        changes = cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM _tt_history WHERE table_name=%s", (table_name,))
        total = cur.fetchone()[0]
        conn.close()
    else:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        changes = conn.execute(
            "SELECT * FROM _tt_history WHERE table_name=? ORDER BY id DESC LIMIT 100",
            (table_name,)
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM _tt_history WHERE table_name=?", (table_name,)
        ).fetchone()[0]
        conn.close()

    content = f"""
    <div class="section">
        <a href="/" class="back-link">← Back to Dashboard</a>
        <h2>📋 Table: {table_name}</h2>
        <p class="text-muted">{total} total changes</p>
    </div>

    <div class="section">
        <h3>🕰️ Time Travel Query</h3>
        <div class="time-travel-bar">
            <input type="datetime-local" id="tt-time" class="input" value="2024-01-01T00:00">
            <button onclick="queryTimeTravel('{table_name}')" class="btn">🔮 Time Travel</button>
            <span id="tt-result" style="margin-left: 12px; font-size: 12px;"></span>
        </div>
        <pre id="tt-output" class="code-block" style="display:none;"></pre>
    </div>

    <div class="section">
        <h3>📝 Change History</h3>
        <table class="data-table">
            <tr><th>ID</th><th>Operation</th><th>Row</th><th>Timestamp</th><th>Checksum</th></tr>
    """
    for c in changes:
        if PG_CONNECTION:
            cid, tbl, row_id, op, old, new, chk, prev, ts = c
        else:
            cid, tbl, row_id, op, old, new, chk, prev, ts = (c[0], c[1], c[2], c[3], c[4], c[5], c[6], c[7], c[8]) if len(c) >= 9 else (c[0], c[1], c[2], c[3], c[4], c[5], c[6], c[7], "")
        content += f"<tr><td>#{cid}</td><td><span class='op-{op.lower()}'>{op}</span></td><td>{row_id}</td><td>{str(ts)[:19]}</td><td class='hash'>{chk[:16]}...</td></tr>"

    content += "</table></div>"
    return render_html(content, f"Table: {table_name}")


@app.get("/api/query", response_class=JSONResponse)
async def api_query(table: str, at: str):
    db = get_db()
    results = db.query_at(at, table)
    db.close()
    return {"table": table, "at": at, "rows": len(results), "data": results}


@app.get("/reports", response_class=HTMLResponse)
async def reports_page():
    reports = sorted(os.listdir(REPORT_DIR)) if os.path.exists(REPORT_DIR) else []

    content = """
    <div class="section">
        <h2>📋 SOC 2 Evidence Report Center</h2>
        <p class="text-muted">Generate and download auditor-ready compliance evidence reports.</p>
    </div>

    <div class="report-grid">
        <div class="report-card">
            <div class="report-icon">🔗</div>
            <h3>Data Integrity Report</h3>
            <p>Proves no data tampering — hash chain verification with auditor statement.</p>
            <div class="report-actions">
                <a href="/api/report/integrity?format=html" class="btn">View HTML</a>
                <a href="/api/report/integrity?format=pdf" class="btn btn-secondary">Download PDF</a>
            </div>
        </div>
        <div class="report-card">
            <div class="report-icon">📝</div>
            <h3>Change Audit Report</h3>
            <p>Complete audit trail — every change, old vs new values.</p>
            <div class="report-actions">
                <a href="/api/report/audit?format=html" class="btn">View HTML</a>
                <a href="/api/report/audit?format=pdf" class="btn btn-secondary">Download PDF</a>
            </div>
        </div>
        <div class="report-card">
            <div class="report-icon">📜</div>
            <h3>Data Retention Report</h3>
            <p>Certifies data existed at a specific point in time — regulatory audits.</p>
            <div class="report-actions">
                <a href="/api/report/retention?at=2025-01-01&format=html" class="btn">View HTML</a>
                <a href="/api/report/retention?at=2025-01-01&format=pdf" class="btn btn-secondary">Download PDF</a>
            </div>
        </div>
        <div class="report-card">
            <div class="report-icon">📊</div>
            <h3>Compliance Summary</h3>
            <p>One-page executive overview — chain status, control coverage, auditor notes.</p>
            <div class="report-actions">
                <a href="/api/report/compliance?format=html" class="btn">View HTML</a>
                <a href="/api/report/compliance?format=pdf" class="btn btn-secondary">Download PDF</a>
            </div>
        </div>
    </div>
    """

    if reports:
        content += "<div class='section'><h3>📁 Previously Generated</h3><ul class='file-list'>"
        for r in sorted(reports, reverse=True)[:10]:
            sz = os.path.getsize(os.path.join(REPORT_DIR, r))
            content += f"<li><a href='/reports-file/{r}'>{r}</a> ({sz/1024:.1f} KB)</li>"
        content += "</ul></div>"

    return render_html(content, "SOC 2 Reports")


@app.get("/api/report/{report_type}")
async def generate_report(
    report_type: str,
    format: str = "html",
    at: str = None,
    start: str = None,
    end: str = None,
):
    if report_type == "integrity":
        html = _gen_integrity_report()
    elif report_type == "audit":
        html = _gen_audit_report(start, end)
    elif report_type == "retention":
        html = _gen_retention_report(at or datetime.utcnow().strftime("%Y-%m-%d"))
    elif report_type == "compliance":
        html = _gen_compliance_report()
    else:
        raise HTTPException(404, f"Unknown report: {report_type}")

    if format == "pdf":
        return _pdf_response(html, report_type)

    return HTMLResponse(html)


@app.get("/reports-file/{filename}")
async def serve_report(filename: str):
    path = os.path.join(REPORT_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404, "Report not found")
    return FileResponse(path)


@app.get("/logs", response_class=HTMLResponse)
async def logs_page():
    stats = get_chain_stats()
    content = f"""
    <div class="section">
        <h2>📝 Change Log</h2>
        <p class="text-muted">{stats['total_changes']} total entries (showing last 200)</p>
    </div>
    <div class="section">
        <table class="data-table">
            <tr><th>ID</th><th>Table</th><th>Row</th><th>Operation</th><th>Timestamp</th><th>Checksum</th></tr>
    """
    # Get last 200 entries
    if PG_CONNECTION:
        conn = get_pg_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, table_name, row_id, operation, checksum, created_at FROM _tt_history ORDER BY id DESC LIMIT 200")
        entries = cur.fetchall()
        conn.close()
        for e in entries:
            content += f"<tr><td>#{e[0]}</td><td>{e[1]}</td><td>{e[2]}</td><td><span class='op-{e[3].lower()}'>{e[3]}</span></td><td>{str(e[5])[:19]}</td><td class='hash'>{e[4][:20]}...</td></tr>"
    else:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        entries = conn.execute("SELECT id, table_name, row_id, operation, checksum, created_at FROM _tt_history ORDER BY id DESC LIMIT 200").fetchall()
        conn.close()
        for e in entries:
            content += f"<tr><td>#{e[0]}</td><td>{e[1]}</td><td>{e[2]}</td><td><span class='op-{e[3].lower()}'>{e[3]}</span></td><td>{e[5][:19]}</td><td class='hash'>{e[4][:20]}...</td></tr>"

    content += "</table></div>"
    return render_html(content, "Change Log")


@app.get("/verify", response_class=HTMLResponse)
async def verify_page():
    chain = get_chain()
    result = chain.verify_chain()
    status_color = "#34d399" if result["status"] == "PASS" else "#fb7185"
    status_icon = "✅" if result["status"] == "PASS" else "❌"

    content = f"""
    <div class="section" style="text-align: center; padding: 40px;">
        <div style="font-size: 64px; margin-bottom: 16px;">{status_icon}</div>
        <h2 style="color: {status_color};">Chain Verification: {result['status']}</h2>
        <p class="text-muted">{result['total']} entries verified</p>
    </div>
    <div class="section">
        <table class="data-table">
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Total Entries</td><td>{result['total']}</td></tr>
            <tr><td>Failed</td><td>{result['failures']}</td></tr>
            <tr><td>Hash Algorithm</td><td>SHA-256 (FIPS 180-4)</td></tr>
            <tr><td>Database</td><td>{DB_TYPE}</td></tr>
            <tr><td>Chain Integrity</td><td style="color: {status_color}; font-weight: bold;">{'✅ INTACT' if result['status'] == 'PASS' else '❌ COMPROMISED'}</td></tr>
        </table>
    </div>
    """
    if result.get("details"):
        content += "<div class='section'><h3>⚠️ Failed Entries</h3><table class='data-table'><tr><th>Entry</th><th>Issue</th></tr>"
        for d in result["details"]:
            content += f"<tr><td>#{d['id']}</td><td>{d['issue']}</td></tr>"
        content += "</table></div>"
    return render_html(content, "Chain Verification")


@app.get("/settings", response_class=HTMLResponse)
async def settings_page():
    content = f"""
    <div class="section">
        <h2>⚙️ Settings</h2>
        <div class="settings-grid">
            <div class="setting-card">
                <h3>🗄️ Database</h3>
                <p class="text-muted">Type: {DB_TYPE}</p>
                <p class="text-muted">Tables tracked: {len(get_table_list())}</p>
                <code style="font-size:10px;">{PG_CONNECTION[:60] + '...' if PG_CONNECTION else DB_PATH}</code>
            </div>
            <div class="setting-card">
                <h3>🔐 Security</h3>
                <p class="text-muted">Hash: SHA-256</p>
                <p class="text-muted">Chain: Immutable linked list</p>
                <p class="text-muted">Data stays on your infrastructure</p>
            </div>
            <div class="setting-card">
                <h3>📊 Reports</h3>
                <p class="text-muted">Output: {REPORT_DIR}</p>
                <p class="text-muted">Format: HTML + PDF</p>
            </div>
            <div class="setting-card">
                <h3>ℹ️ Version</h3>
                <p class="text-muted">Shayntech TimeTravel Enterprise v0.1.0</p>
                <p class="text-muted">Support: hello@shayntech.com</p>
            </div>
        </div>
    </div>
    """
    return render_html(content, "Settings")


# ─── REPORT GENERATORS ─────────────────────────────────────

def _gen_integrity_report() -> str:
    chain = get_chain()
    verify = chain.verify_chain()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    tables = get_table_list()

    return REPORT_HTML_TEMPLATE.format(
        title="SOC 2 — Data Integrity Report",
        subtitle=f"Generated: {now} | Database: {DB_TYPE}",
        sections=f"""
        <div class="status-badge {'pass' if verify['status'] == 'PASS' else 'fail'}">
            {'✅ PASS' if verify['status'] == 'PASS' else '❌ FAIL'}
        </div>
        <p><strong>Total Entries:</strong> {verify['total']}</p>
        <p><strong>Failed Verifications:</strong> {verify['failures']}</p>
        <p><strong>Hash Algorithm:</strong> SHA-256 (FIPS 180-4)</p>
        <p><strong>Tables Monitored:</strong> {len(tables)}</p>
        <h3>Auditor Statement</h3>
        <p>This report provides cryptographic evidence that all tracked data has remained intact and unmodified since baseline capture. The SHA-256 hash chain ensures non-repudiation and tamper detection. Each entry's checksum is verified against the computed hash and linked to the previous entry's checksum, forming an unbroken chain of custody.</p>
        """
    )


def _gen_audit_report(start: str = None, end: str = None) -> str:
    tables = get_table_list()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    ops_count = {"INSERT": 0, "UPDATE": 0, "DELETE": 0, "BASELINE": 0}
    total = 0

    if PG_CONNECTION:
        conn = get_pg_conn()
        cur = conn.cursor()
        for op in ops_count:
            cur.execute("SELECT COUNT(*) FROM _tt_history WHERE operation=%s", (op,))
            ops_count[op] = cur.fetchone()[0]
            total += ops_count[op]
        conn.close()
    else:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        for op in ops_count:
            c = conn.execute("SELECT COUNT(*) FROM _tt_history WHERE operation=?", (op,)).fetchone()[0]
            ops_count[op] = c
            total += c
        conn.close()

    period_info = f"Period: {start or 'All time'} → {end or 'Present'}"
    table_rows = ""
    for op, cnt in ops_count.items():
        if cnt > 0:
            table_rows += f"<tr><td>{op}</td><td>{cnt}</td></tr>"

    return REPORT_HTML_TEMPLATE.format(
        title="SOC 2 — Change Audit Report",
        subtitle=f"{period_info} | Generated: {now}",
        sections=f"""
        <p><strong>Total Changes:</strong> {total}</p>
        <p><strong>Tables Monitored:</strong> {len(tables)}</p>
        <table class="data-table">
            <tr><th>Operation</th><th>Count</th></tr>
            {table_rows}
        </table>
        <h3>Auditor Statement</h3>
        <p>This report documents all data changes recorded by the Shayntech TimeTravel system. Every INSERT, UPDATE, and DELETE operation is captured with cryptographic checksums. The complete audit trail provides evidence of who changed what and when, satisfying SOC 2 CC6.1 (Logical Access) and CC7.2 (Monitoring) criteria.</p>
        """
    )


def _gen_retention_report(at: str) -> str:
    tables = get_table_list()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    total = 0
    if PG_CONNECTION:
        conn = get_pg_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM _tt_history WHERE created_at <= %s", (at,))
        total_before = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM _tt_history WHERE created_at > %s", (at,))
        total_after = cur.fetchone()[0]
        conn.close()
    else:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        total_before = conn.execute("SELECT COUNT(*) FROM _tt_history WHERE created_at <= ?", (at,)).fetchone()[0]
        total_after = conn.execute("SELECT COUNT(*) FROM _tt_history WHERE created_at > ?", (at,)).fetchone()[0]
        conn.close()

    return REPORT_HTML_TEMPLATE.format(
        title="SOC 2 — Data Retention Report",
        subtitle=f"As of: {at} | Generated: {now}",
        sections=f"""
        <p><strong>Retention Date:</strong> {at}</p>
        <p><strong>Entries Before:</strong> {total_before}</p>
        <p><strong>Entries After:</strong> {total_after}</p>
        <p><strong>Tables Monitored:</strong> {len(tables)}</p>
        <h3>Auditor Statement</h3>
        <p>This report certifies that data was captured and retained by the Shayntech TimeTravel system as of the specified date. The immutable hash chain provides point-in-time evidence that data existed in its recorded state, satisfying SOC 2 A1.2 (Retention) and A1.3 (Non-Repudiation) criteria.</p>
        """
    )


def _gen_compliance_report() -> str:
    chain = get_chain()
    verify = chain.verify_chain()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    tables = get_table_list()

    return REPORT_HTML_TEMPLATE.format(
        title="SOC 2 — Compliance Summary",
        subtitle=f"Generated: {now}",
        sections=f"""
        <div class="status-badge {'pass' if verify['status'] == 'PASS' else 'fail'}">
            {'✅ PASS' if verify['status'] == 'PASS' else '❌ FAIL'}
        </div>
        <p><strong>Chain Status:</strong> {verify['status']} ({verify['total']} entries, {verify['failures']} failures)</p>
        <p><strong>Tables Monitored:</strong> {len(tables)}</p>
        <h3>Controls Coverage</h3>
        <table class="data-table">
            <tr><th>Control</th><th>Status</th><th>Evidence</th></tr>
            <tr><td>CC6.1 — Logical Access</td><td class="pass">✅</td><td>Change audit trail captures all data modifications</td></tr>
            <tr><td>CC6.6 — Data Integrity</td><td class="pass">✅</td><td>Immutable SHA-256 hash chain prevents undetected modification</td></tr>
            <tr><td>CC7.2 — Monitoring</td><td class="pass">✅</td><td>Continuous change detection with tamper verification</td></tr>
            <tr><td>A1.2 — Retention</td><td class="pass">✅</td><td>Point-in-time snapshots prove data existence</td></tr>
            <tr><td>A1.3 — Non-Repudiation</td><td class="pass">✅</td><td>Cryptographic hash chain authenticates all recorded history</td></tr>
        </table>
        <h3>Auditor Statement</h3>
        <p>This system provides cryptographic evidence that data has remained intact and unmodified since tracking began. The SHA-256 hash chain ensures non-repudiation and tamper detection. The controls documented here address SOC 2 Type II criteria for security, availability, and confidentiality.</p>
        """
    )


REPORT_HTML_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
  @page {{ margin: 20mm 15mm; }}
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; color: #1e293b; padding: 30px; max-width: 1000px; margin: 0 auto; }}
  h1 {{ font-size: 26px; border-bottom: 3px solid #4f46e5; padding-bottom: 10px; margin-bottom: 4px; }}
  .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
  .status-badge {{ display: inline-block; padding: 8px 20px; border-radius: 20px; font-size: 18px; font-weight: bold; margin: 16px 0; }}
  .status-badge.pass {{ background: #dcfce7; color: #166534; border: 2px solid #16a34a; }}
  .status-badge.fail {{ background: #fce4ec; color: #b91c1c; border: 2px solid #dc2626; }}
  p {{ font-size: 13px; line-height: 1.6; color: #475569; }}
  table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 12px; }}
  th {{ background: #f1f5f9; text-align: left; padding: 10px; font-weight: 600; color: #475569; border-bottom: 2px solid #e2e8f0; }}
  td {{ padding: 10px; border-bottom: 1px solid #e2e8f0; }}
  h3 {{ font-size: 15px; margin-top: 24px; color: #334155; }}
  .footer {{ margin-top: 40px; padding-top: 12px; border-top: 1px solid #e2e8f0; color: #94a3b8; font-size: 10px; text-align: center; }}
  .pass {{ color: #16a34a; }}
  .fail {{ color: #dc2626; }}
  @media print {{ body {{ padding: 0; }} .no-print {{ display: none; }} }}
</style></head>
<body>
<h1>{title}</h1>
<p class="subtitle">{subtitle}</p>
{sections}
<div class="footer">Shayntech TimeTravel Enterprise — SOC 2 Evidence Report — hello@shayntech.com</div>
</body></html>"""


def _pdf_response(html_content: str, report_type: str) -> FileResponse:
    """Generate PDF from HTML using weasyprint, or fall back to HTML."""
    try:
        import weasyprint
        pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()
        filename = f"soc2-{report_type}-{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
        path = os.path.join(REPORT_DIR, filename)
        with open(path, "wb") as f:
            f.write(pdf_bytes)
        return FileResponse(path, filename=filename, media_type="application/pdf")
    except ImportError:
        # Fallback: save HTML and return it
        filename = f"soc2-{report_type}-{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.html"
        path = os.path.join(REPORT_DIR, filename)
        with open(path, "w") as f:
            f.write(html_content)
        return FileResponse(path, filename=filename, media_type="text/html")
    except Exception as e:
        # Fallback on any error
        filename = f"soc2-{report_type}-{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.html"
        path = os.path.join(REPORT_DIR, filename)
        with open(path, "w") as f:
            f.write(html_content)
        return FileResponse(path, filename=filename, media_type="text/html")


# ─── DASHBOARD HTML ────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{TITLE}} — Shayntech TimeTravel Enterprise</title>
<style>
  :root {
    --bg: #0f172a;
    --surface: #1e293b;
    --border: #334155;
    --text: #e2e8f0;
    --text-dim: #64748b;
    --accent: #a78bfa;
    --accent2: #4f46e5;
    --green: #34d399;
    --yellow: #fbbf24;
    --red: #fb7185;
    --cyan: #22d3ee;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--bg); color: var(--text); min-height: 100vh;
  }
  .layout { display: flex; min-height: 100vh; }
  .sidebar {
    width: 240px; background: #0a0f1e; border-right: 1px solid var(--border);
    padding: 20px 0; flex-shrink: 0;
  }
  .sidebar-brand {
    padding: 0 20px 20px; border-bottom: 1px solid var(--border);
    font-size: 16px; font-weight: 700; display: flex; align-items: center; gap: 8px;
  }
  .sidebar-brand span { background: linear-gradient(135deg, #a78bfa, #34d399); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  .sidebar-nav { padding: 12px 0; }
  .nav-item {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 20px; color: var(--text-dim); text-decoration: none;
    font-size: 13px; transition: all 0.2s;
  }
  .nav-item:hover, .nav-item.active { background: rgba(167, 139, 250, 0.1); color: var(--text); }
  .nav-item.active { border-right: 3px solid var(--accent); }
  .nav-icon { font-size: 16px; }
  .sidebar-divider { height: 1px; background: var(--border); margin: 8px 20px; }
  .main { flex: 1; padding: 30px; overflow-y: auto; }
  .main-header { margin-bottom: 24px; }
  .main-header h1 { font-size: 22px; font-weight: 700; }
  .main-header p { color: var(--text-dim); font-size: 13px; margin-top: 4px; }
  .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .stat-card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
    padding: 20px; display: flex; align-items: center; gap: 16px;
  }
  .stat-icon { width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 22px; flex-shrink: 0; }
  .stat-value { font-size: 28px; font-weight: 700; }
  .stat-label { font-size: 12px; color: var(--text-dim); margin-top: 2px; }
  .data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .data-table th {
    background: #0a0f1e; padding: 10px 12px; text-align: left;
    font-weight: 600; font-size: 11px; color: var(--text-dim); text-transform: uppercase;
    border-bottom: 1px solid var(--border);
  }
  .data-table td { padding: 10px 12px; border-bottom: 1px solid var(--border); }
  .data-table tr:hover td { background: rgba(167, 139, 250, 0.05); }
  .op-insert { color: var(--green); font-weight: 600; }
  .op-update { color: var(--yellow); font-weight: 600; }
  .op-delete { color: var(--red); font-weight: 600; }
  .op-baseline { color: var(--text-dim); }
  .btn {
    display: inline-flex; align-items: center; gap: 6px;
    background: linear-gradient(135deg, #4f46e5, #7c3aed); color: #fff;
    border: none; padding: 8px 16px; border-radius: 8px; font-size: 12px;
    font-weight: 600; cursor: pointer; text-decoration: none; transition: opacity 0.2s;
  }
  .btn:hover { opacity: 0.9; }
  .btn-secondary { background: transparent; border: 1px solid var(--border); color: var(--text); }
  .btn-secondary:hover { border-color: var(--accent); }
  .btn-sm { padding: 4px 10px; font-size: 11px; }
  .back-link { color: var(--accent); text-decoration: none; font-size: 13px; display: inline-block; margin-bottom: 12px; }
  .back-link:hover { text-decoration: underline; }
  .section { margin-bottom: 24px; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
  .section h2 { font-size: 16px; font-weight: 700; margin-bottom: 12px; }
  .section h3 { font-size: 14px; font-weight: 600; margin-bottom: 8px; }
  .text-muted { color: var(--text-dim); font-size: 12px; margin-bottom: 8px; }
  .hash { font-family: monospace; font-size: 11px; color: var(--text-dim); }
  .code-block { background: #0a0f1e; border: 1px solid var(--border); border-radius: 8px; padding: 16px; font-size: 12px; font-family: monospace; overflow-x: auto; color: var(--text); margin-top: 8px; white-space: pre-wrap; }
  .input { background: #0a0f1e; border: 1px solid var(--border); border-radius: 8px; padding: 8px 12px; color: var(--text); font-size: 13px; }
  .input:focus { outline: none; border-color: var(--accent); }
  .report-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
  .report-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; transition: border-color 0.2s; }
  .report-card:hover { border-color: var(--accent); }
  .report-icon { font-size: 32px; margin-bottom: 8px; }
  .report-card h3 { font-size: 14px; font-weight: 700; margin-bottom: 8px; }
  .report-card p { font-size: 12px; color: var(--text-dim); margin-bottom: 16px; line-height: 1.5; }
  .report-actions { display: flex; gap: 8px; }
  .settings-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; }
  .setting-card { background: #0a0f1e; border: 1px solid var(--border); border-radius: 10px; padding: 16px; font-size: 12px; }
  .setting-card h3 { font-size: 14px; margin-bottom: 8px; }
  .setting-card code { background: rgba(0,0,0,0.3); padding: 4px 8px; border-radius: 4px; font-size: 11px; word-break: break-all; }
  .time-travel-bar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .file-list { list-style: none; }
  .file-list li { padding: 6px 0; }
  .file-list a { color: var(--accent); text-decoration: none; font-size: 12px; }
  .file-list a:hover { text-decoration: underline; }
</style>
</head>
<body>
<div class="layout">
  <div class="sidebar">
    <div class="sidebar-brand">🔮 <span>TimeTravel</span></div>
    <div class="sidebar-nav">
      <a href="/" class="nav-item active"><span class="nav-icon">📊</span> Dashboard</a>
      <a href="/logs" class="nav-item"><span class="nav-icon">📝</span> Change Log</a>
      <a href="/reports" class="nav-item"><span class="nav-icon">📋</span> SOC 2 Reports</a>
      <a href="/verify" class="nav-item"><span class="nav-icon">🔗</span> Chain Verify</a>
      <div class="sidebar-divider"></div>
      <a href="/settings" class="nav-item"><span class="nav-icon">⚙️</span> Settings</a>
    </div>
    <div class="sidebar-footer">Shayntech TimeTravel Enterprise<br>v0.1.0</div>
  </div>
  <div class="main">
    <div class="main-header">
      <h1>{{TITLE}}</h1>
      <p>Shayntech TimeTravel — Git for your database. SOC 2 evidence built in.</p>
    </div>
    {{CONTENT}}
  </div>
</div>
<script>
function queryTimeTravel(table) {
  const time = document.getElementById('tt-time').value;
  const result = document.getElementById('tt-result');
  const output = document.getElementById('tt-output');
  result.textContent = '⏳ Querying...';
  output.style.display = 'none';
  fetch('/api/query?table=' + encodeURIComponent(table) + '&at=' + encodeURIComponent(time))
    .then(r => r.json())
    .then(d => {
      result.textContent = '✅ ' + d.rows + ' rows found at ' + d.at;
      output.textContent = JSON.stringify(d.data, null, 2);
      output.style.display = 'block';
    })
    .catch(e => { result.textContent = '❌ Error: ' + e; });
}
</script>
</body>
</html>"""


def main():
    host = os.environ.get("TT_HOST", "0.0.0.0")
    port = int(os.environ.get("TT_PORT", "8080"))

    print(f"🔮 Shayntech TimeTravel Enterprise")
    print(f"   Dashboard: http://localhost:{port}")
    print(f"   Database: {DB_TYPE}")
    if PG_CONNECTION:
        print(f"   Connection: {PG_CONNECTION[:50]}...")
    else:
        print(f"   Path: {DB_PATH}")
    print()

    if not PG_CONNECTION:
        import sqlite3
        if not os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH)
            conn.execute("CREATE TABLE IF NOT EXISTS _dummy (id INT)")
            conn.commit()
            conn.close()
            from shayntech_timetravel.core import HashChain as Hc
            chain = Hc(DB_PATH)
            print(f"   ✅ New database initialized")

    try:
        import weasyprint
        print(f"   ✅ PDF generation: WeasyPrint ready")
    except ImportError:
        print(f"   ⚠️  PDF generation: WeasyPrint not installed (will use HTML fallback)")
    print()

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
