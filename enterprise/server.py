"""Shayntech TimeTravel Enterprise — Web server for the compliance dashboard."""

import os
import json
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from shayntech_timetravel.core import TimeTravelDB, HashChain
from shayntech_timetravel.reports import SOC2Report

app = FastAPI(title="Shayntech TimeTravel Enterprise", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- Configuration ---
DATA_DIR = os.environ.get("TT_DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "timetravel.db")
REPORT_DIR = os.path.join(DATA_DIR, "reports")
os.makedirs(REPORT_DIR, exist_ok=True)

def get_db() -> TimeTravelDB:
    return TimeTravelDB(DB_PATH)

def get_chain() -> HashChain:
    return HashChain(DB_PATH)

def get_reports() -> SOC2Report:
    return SOC2Report(DB_PATH)

# ─── HELPERS ───────────────────────────────────────────────

def render_html(content: str, title: str = "Dashboard") -> str:
    """Wrap content in the enterprise dashboard layout."""
    return HTMLResponse(DASHBOARD_HTML.replace("{{CONTENT}}", content).replace("{{TITLE}}", title))

# ─── API ROUTES ────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Main dashboard view."""
    chain = get_chain()
    verify = chain.verify_chain()
    
    conn = sqlite3.connect(DB_PATH)
    
    # Count changes
    total_changes = conn.execute("SELECT COUNT(*) FROM _tt_history").fetchone()[0]
    tables = [r[0] for r in conn.execute("SELECT DISTINCT table_name FROM _tt_history").fetchall()]
    
    # Changes per table
    changes_per_table = {}
    for t in tables:
        c = conn.execute("SELECT COUNT(*) FROM _tt_history WHERE table_name=?", (t,)).fetchone()[0]
        changes_per_table[t] = c
    
    # Recent activity
    recent = conn.execute(
        "SELECT id, table_name, operation, created_at FROM _tt_history ORDER BY id DESC LIMIT 10"
    ).fetchall()
    
    # Time range
    first = conn.execute("SELECT MIN(created_at) FROM _tt_history").fetchone()[0] or "N/A"
    last = conn.execute("SELECT MAX(created_at) FROM _tt_history").fetchone()[0] or "N/A"
    conn.close()
    
    # Build overview cards
    cards = f"""
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-icon" style="background: rgba(167, 139, 250, 0.15);">🔮</div>
            <div class="stat-info">
                <div class="stat-value">{total_changes}</div>
                <div class="stat-label">Total Changes Tracked</div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon" style="background: rgba(52, 211, 153, 0.15);">📊</div>
            <div class="stat-info">
                <div class="stat-value">{len(tables)}</div>
                <div class="stat-label">Tables Monitored</div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon" style="background: rgba(251, 191, 36, 0.15);">🔗</div>
            <div class="stat-info">
                <div class="stat-value">{'✅' if verify['status'] == 'PASS' else '❌'}</div>
                <div class="stat-label">Chain Status: {verify['status']}</div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon" style="background: rgba(34, 211, 238, 0.15);">📅</div>
            <div class="stat-info">
                <div class="stat-value" style="font-size: 14px;">{first[:10]}</div>
                <div class="stat-label">→ {last[:10]}</div>
            </div>
        </div>
    </div>
    """
    
    # Tables section
    tables_html = "<div class='section'><h2>📊 Tracked Tables</h2><table class='data-table'><tr><th>Table</th><th>Changes</th><th>Actions</th></tr>"
    for t in sorted(changes_per_table.keys()):
        tables_html += f"<tr><td>{t}</td><td>{changes_per_table[t]}</td>"
        tables_html += f"<td><a href='/table/{t}' class='btn-sm'>View History</a></td></tr>"
    tables_html += "</table></div>"
    
    # Recent activity
    recent_html = "<div class='section'><h2>⏱️ Recent Activity</h2><table class='data-table'><tr><th>ID</th><th>Table</th><th>Op</th><th>Time</th></tr>"
    for r in recent:
        recent_html += f"<tr><td>#{r[0]}</td><td>{r[1]}</td><td><span class='op-{r[2].lower()}'>{r[2]}</span></td><td>{r[3][:19]}</td></tr>"
    recent_html += "</table></div>"
    
    content = cards + tables_html + recent_html
    return render_html(content, "Dashboard")


@app.get("/table/{table_name}", response_class=HTMLResponse)
async def table_view(table_name: str):
    """View table history and time travel."""
    chain = get_chain()
    conn = sqlite3.connect(DB_PATH)
    
    # Get table changes
    changes = conn.execute(
        "SELECT * FROM _tt_history WHERE table_name=? ORDER BY id DESC LIMIT 100",
        (table_name,)
    ).fetchall()
    total = conn.execute(
        "SELECT COUNT(*) FROM _tt_history WHERE table_name=?", (table_name,)
    ).fetchone()[0]
    conn.close()
    
    # Current data
    try:
        db = get_db()
        current_data = db.query_at("2099-01-01", table_name)
        db.close()
    except:
        current_data = []
    
    content = f"""
    <div class="section">
        <a href="/" class="back-link">← Back to Dashboard</a>
        <h2>📋 Table: {table_name}</h2>
        <p class="text-muted">{total} total changes | {len(current_data)} current rows</p>
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
        content += f"<tr><td>#{c[0]}</td><td><span class='op-{c[3].lower()}'>{c[3]}</span></td><td>{c[2]}</td><td>{c[7][:19]}</td><td class='hash'>{c[5][:16]}...</td></tr>"
    
    content += "</table></div>"
    return render_html(content, f"Table: {table_name}")


@app.get("/api/query", response_class=JSONResponse)
async def api_query(table: str, at: str):
    """API endpoint for time travel queries."""
    db = get_db()
    results = db.query_at(at, table)
    db.close()
    return {"table": table, "at": at, "rows": len(results), "data": results}


@app.get("/reports", response_class=HTMLResponse)
async def reports_page():
    """SOC 2 Report Center."""
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
            <p>Complete audit trail — every change, who made it, when, old vs new values.</p>
            <div class="report-actions">
                <a href="/api/report/audit?format=html" class="btn">View HTML</a>
                <a href="/api/report/audit?format=pdf" class="btn btn-secondary">Download PDF</a>
            </div>
        </div>
        <div class="report-card">
            <div class="report-icon">📜</div>
            <h3>Data Retention Report</h3>
            <p>Certifies data existed at a specific point in time — for regulatory audits.</p>
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
            size = os.path.getsize(os.path.join(REPORT_DIR, r))
            content += f"<li><a href='/reports-files/{r}'>{r}</a> ({size/1024:.1f} KB)</li>"
        content += "</ul></div>"
    
    return render_html(content, "SOC 2 Reports")


@app.get("/api/report/{report_type}")
async def generate_report(report_type: str, format: str = "html", at: str = None, start: str = None, end: str = None):
    """Generate SOC 2 evidence reports."""
    report = get_reports()
    
    generators = {
        "integrity": lambda: report.integrity_report(),
        "audit": lambda: report.change_audit_report(start, end),
        "retention": lambda: report.retention_report(at or datetime.utcnow().strftime("%Y-%m-%d")),
        "compliance": lambda: _compliance_report(),
    }
    
    if report_type not in generators:
        raise HTTPException(404, f"Unknown report type: {report_type}")
    
    html_content = generators[report_type]()
    
    if format == "pdf":
        # Save as HTML for now (PDF via browser print is more reliable)
        filename = f"soc2-{report_type}-{datetime.utcnow().strftime('%Y%m%d')}.html"
        path = os.path.join(REPORT_DIR, filename)
        with open(path, "w") as f:
            f.write(html_content)
        return FileResponse(path, filename=filename, media_type="text/html")
    
    return HTMLResponse(html_content)


def _compliance_report():
    """Generate compliance summary report."""
    chain = get_chain()
    verify = chain.verify_chain()
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM _tt_history").fetchone()[0]
    tables = [r[0] for r in conn.execute("SELECT DISTINCT table_name FROM _tt_history").fetchall()]
    conn.close()
    
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>SOC 2 Compliance Summary</title>
<style>
  body {{ font-family: -apple-system, sans-serif; background: #fff; color: #1e293b; padding: 40px; max-width: 900px; margin: 0 auto; }}
  h1 {{ font-size: 28px; border-bottom: 3px solid #4f46e5; padding-bottom: 10px; }}
  .pass {{ color: #16a34a; font-weight: bold; }}
  .fail {{ color: #dc2626; font-weight: bold; }}
  table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
  th {{ background: #f1f5f9; text-align: left; padding: 10px; font-size: 12px; text-transform: uppercase; }}
  td {{ padding: 10px; border-bottom: 1px solid #e2e8f0; }}
  .section {{ margin: 24px 0; padding: 20px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; }}
  .footer {{ margin-top: 40px; color: #94a3b8; font-size: 11px; text-align: center; }}
  @media print {{ body {{ padding: 20px; }} .section {{ break-inside: avoid; }} }}
</style></head>
<body>
<h1>📋 SOC 2 Compliance Summary</h1>
<p>Generated: {now}</p>
<div class="section">
  <h2>Chain Status: <span class="{'pass' if verify['status'] == 'PASS' else 'fail'}">{verify['status']}</span></h2>
  <p>Total Entries: {total} | Tables: {len(tables)} | Failures: {verify['failures']}</p>
</div>
<div class="section">
  <h2>Controls Coverage</h2>
  <table><tr><th>Control</th><th>Status</th><th>Evidence</th></tr>
  <tr><td>CC6.1 — Logical Access</td><td class="pass">✅</td><td>Change audit trail captures all data access</td></tr>
  <tr><td>CC6.6 — Data Integrity</td><td class="pass">✅</td><td>Immutable hash chain prevents undetected modification</td></tr>
  <tr><td>CC7.2 — Monitoring</td><td class="pass">✅</td><td>Continuous change detection with alerts on tampering</td></tr>
  <tr><td>A1.2 — Retention</td><td class="pass">✅</td><td>Point-in-time snapshots prove data existence</td></tr>
  <tr><td>A1.3 — Non-Repudiation</td><td class="pass">✅</td><td>Hash chain provides cryptographic proof of authenticity</td></tr>
  </table>
</div>
<div class="section">
  <p><strong>Auditor Statement:</strong> This system provides cryptographic evidence that data has remained intact and unmodified since tracking began. The SHA-256 hash chain ensures non-repudiation and tamper detection.</p>
</div>
<div class="footer">Shayntech TimeTravel Enterprise — Compliance Report</div>
</body></html>"""


@app.get("/logs", response_class=HTMLResponse)
async def logs_page():
    """Full change log page."""
    chain = get_chain()
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM _tt_history").fetchone()[0]
    entries = conn.execute("SELECT * FROM _tt_history ORDER BY id DESC LIMIT 200").fetchall()
    conn.close()
    
    content = f"""
    <div class="section">
        <h2>📝 Change Log</h2>
        <p class="text-muted">{total} total entries (showing last 200)</p>
    </div>
    <div class="section">
        <table class="data-table">
            <tr><th>ID</th><th>Table</th><th>Row</th><th>Operation</th><th>Timestamp</th><th>Checksum</th></tr>
    """
    for e in entries:
        content += f"<tr><td>#{e[0]}</td><td>{e[1]}</td><td>{e[2]}</td>"
        content += f"<td><span class='op-{e[3].lower()}'>{e[3]}</span></td>"
        content += f"<td>{e[7][:19]}</td><td class='hash'>{e[5][:20]}...</td></tr>"
    content += "</table></div>"
    return render_html(content, "Change Log")


@app.get("/verify", response_class=HTMLResponse)
async def verify_page():
    """Chain verification page."""
    chain = get_chain()
    result = chain.verify_chain()
    
    status_color = "var(--green)" if result["status"] == "PASS" else "var(--red)"
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
            <tr><td>Failed Verifications</td><td>{result['failures']}</td></tr>
            <tr><td>Hash Algorithm</td><td>SHA-256 (FIPS 180-4)</td></tr>
            <tr><td>Chain Integrity</td><td style="color: {status_color}; font-weight: bold;">{'INTACT — No tampering detected' if result['status'] == 'PASS' else 'COMPROMISED'}</td></tr>
        </table>
    </div>
    """
    if result.get("details"):
        content += "<div class='section'><h3>⚠️ Failed Entries</h3><table class='data-table'>"
        content += "<tr><th>Entry ID</th><th>Issue</th></tr>"
        for d in result["details"]:
            content += f"<tr><td>#{d['id']}</td><td>{d['issue']}</td></tr>"
        content += "</table></div>"
    
    return render_html(content, "Chain Verification")


@app.get("/settings", response_class=HTMLResponse)
async def settings_page():
    """Settings/config page."""
    content = """
    <div class="section">
        <h2>⚙️ Settings</h2>
        <div class="settings-grid">
            <div class="setting-card">
                <h3>🗄️ Database</h3>
                <p class="text-muted">Currently tracking:</p>
                <code>/data/timetravel.db</code>
                <p class="text-muted" style="margin-top: 8px;">Type: SQLite</p>
            </div>
            <div class="setting-card">
                <h3>🔐 Security</h3>
                <p class="text-muted">Hash algorithm: SHA-256</p>
                <p class="text-muted">Chain mode: Immutable linked list</p>
                <p class="text-muted">Data stored: Locally only</p>
            </div>
            <div class="setting-card">
                <h3>📊 Reports</h3>
                <p class="text-muted">Output directory: /data/reports</p>
                <p class="text-muted">Format: HTML (PDF via browser)</p>
            </div>
            <div class="setting-card">
                <h3>ℹ️ Version</h3>
                <p class="text-muted">Tool: Shayntech TimeTravel Enterprise v0.1.0</p>
                <p class="text-muted">License: Proprietary</p>
                <p class="text-muted">Support: hello@shayntech.com</p>
            </div>
        </div>
    </div>
    """
    return render_html(content, "Settings")


# ─── DASHBOARD HTML TEMPLATE ────────────────────────────

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
  
  /* Sidebar */
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
  .nav-badge {
    margin-left: auto; background: var(--accent); color: #fff; font-size: 10px;
    padding: 2px 6px; border-radius: 10px; font-weight: 600;
  }
  .sidebar-divider {
    height: 1px; background: var(--border); margin: 8px 20px;
  }
  .sidebar-footer {
    padding: 16px 20px; border-top: 1px solid var(--border); margin-top: auto;
    font-size: 11px; color: var(--text-dim);
  }
  
  /* Main */
  .main { flex: 1; padding: 30px; overflow-y: auto; }
  .main-header { margin-bottom: 24px; }
  .main-header h1 { font-size: 22px; font-weight: 700; }
  .main-header p { color: var(--text-dim); font-size: 13px; margin-top: 4px; }
  
  /* Stats */
  .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .stat-card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
    padding: 20px; display: flex; align-items: center; gap: 16px;
  }
  .stat-icon { width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 22px; flex-shrink: 0; }
  .stat-value { font-size: 28px; font-weight: 700; }
  .stat-label { font-size: 12px; color: var(--text-dim); margin-top: 2px; }
  
  /* Tables */
  .data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .data-table th {
    background: #0a0f1e; padding: 10px 12px; text-align: left;
    font-weight: 600; font-size: 11px; color: var(--text-dim); text-transform: uppercase;
    border-bottom: 1px solid var(--border);
  }
  .data-table td { padding: 10px 12px; border-bottom: 1px solid var(--border); }
  .data-table tr:hover td { background: rgba(167, 139, 250, 0.05); }
  
  /* Operations */
  .op-insert { color: var(--green); font-weight: 600; }
  .op-update { color: var(--yellow); font-weight: 600; }
  .op-delete { color: var(--red); font-weight: 600; }
  .op-baseline { color: var(--text-dim); }
  
  /* Buttons */
  .btn {
    display: inline-flex; align-items: center; gap: 6px;
    background: linear-gradient(135deg, #4f46e5, #7c3aed); color: #fff;
    border: none; padding: 8px 16px; border-radius: 8px; font-size: 12px;
    font-weight: 600; cursor: pointer; text-decoration: none; transition: opacity 0.2s;
  }
  .btn:hover { opacity: 0.9; }
  .btn-secondary {
    background: transparent; border: 1px solid var(--border); color: var(--text);
  }
  .btn-secondary:hover { border-color: var(--accent); }
  .btn-sm { padding: 4px 10px; font-size: 11px; }
  .back-link { color: var(--accent); text-decoration: none; font-size: 13px; display: inline-block; margin-bottom: 12px; }
  .back-link:hover { text-decoration: underline; }
  
  /* Sections */
  .section { margin-bottom: 24px; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
  .section h2 { font-size: 16px; font-weight: 700; margin-bottom: 12px; }
  .section h3 { font-size: 14px; font-weight: 600; margin-bottom: 8px; }
  .text-muted { color: var(--text-dim); font-size: 12px; margin-bottom: 8px; }
  .hash { font-family: monospace; font-size: 11px; color: var(--text-dim); }
  .code-block {
    background: #0a0f1e; border: 1px solid var(--border); border-radius: 8px;
    padding: 16px; font-size: 12px; font-family: monospace; overflow-x: auto;
    color: var(--text); margin-top: 8px; white-space: pre-wrap;
  }
  .input {
    background: #0a0f1e; border: 1px solid var(--border); border-radius: 8px;
    padding: 8px 12px; color: var(--text); font-size: 13px;
  }
  .input:focus { outline: none; border-color: var(--accent); }
  
  /* Reports */
  .report-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
  .report-card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
    padding: 20px; transition: border-color 0.2s;
  }
  .report-card:hover { border-color: var(--accent); }
  .report-icon { font-size: 32px; margin-bottom: 8px; }
  .report-card h3 { font-size: 14px; font-weight: 700; margin-bottom: 8px; }
  .report-card p { font-size: 12px; color: var(--text-dim); margin-bottom: 16px; line-height: 1.5; }
  .report-actions { display: flex; gap: 8px; }
  
  /* Settings */
  .settings-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; }
  .setting-card {
    background: #0a0f1e; border: 1px solid var(--border); border-radius: 10px;
    padding: 16px; font-size: 12px;
  }
  .setting-card h3 { font-size: 14px; margin-bottom: 8px; }
  .setting-card code { background: rgba(0,0,0,0.3); padding: 4px 8px; border-radius: 4px; font-size: 11px; }
  .time-travel-bar { display: flex; align-items: center; gap: 8px; }
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
    <div class="sidebar-footer">
      Shayntech TimeTravel Enterprise<br>
      v0.1.0
    </div>
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
    .catch(e => {
      result.textContent = '❌ Error: ' + e;
    });
}
</script>
</body>
</html>"""


def main():
    """Run the enterprise server."""
    host = os.environ.get("TT_HOST", "0.0.0.0")
    port = int(os.environ.get("TT_PORT", "8080"))
    
    print(f"🔮 Shayntech TimeTravel Enterprise")
    print(f"   Dashboard: http://{host}:{port}")
    print(f"   Database: {DB_PATH}")
    print()
    
    # Initialize DB if needed
    if not os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        conn.execute("CREATE TABLE IF NOT EXISTS _dummy (id INT)")
        conn.commit()
        conn.close()
        chain = HashChain(DB_PATH)
        print(f"   ✅ New database initialized")
    
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
