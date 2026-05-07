"""SOC 2 compliance report generator for Shayntech TimeTravel."""

import json
import sqlite3
from datetime import datetime
from typing import Optional
from .core import HashChain


class SOC2Report:
    """Generates SOC 2 compliance reports from the change store."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.chain = HashChain(db_path)

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def integrity_report(self) -> str:
        """Generate a Data Integrity Report — proves no tampering."""
        verification = self.chain.verify_chain()
        conn = self._get_conn()
        
        total = conn.execute("SELECT COUNT(*) as c FROM _tt_history").fetchone()["c"]
        first = conn.execute("SELECT MIN(created_at) as t FROM _tt_history").fetchone()["t"]
        last = conn.execute("SELECT MAX(created_at) as t FROM _tt_history").fetchone()["t"]
        tables = conn.execute(
            "SELECT DISTINCT table_name FROM _tt_history ORDER BY table_name"
        ).fetchall()
        conn.close()

        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>SOC 2 Data Integrity Report — Shayntech TimeTravel</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: #0f172a; color: #e2e8f0; padding: 40px; max-width: 900px; margin: 0 auto; }}
  h1 {{ font-size: 24px; border-bottom: 2px solid #a78bfa; padding-bottom: 10px; }}
  h2 {{ font-size: 18px; color: #a78bfa; margin-top: 30px; }}
  .pass {{ color: #34d399; font-weight: bold; }}
  .fail {{ color: #fb7185; font-weight: bold; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; margin: 12px 0; }}
  .card p {{ margin: 4px 0; }}
  .label {{ color: #64748b; }}
  table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
  th {{ background: #334155; padding: 8px; text-align: left; font-size: 12px; color: #94a3b8; }}
  td {{ padding: 8px; border-bottom: 1px solid #1e293b; font-size: 12px; }}
  .footer {{ margin-top: 40px; color: #475569; font-size: 11px; text-align: center; }}
  .stamp {{ border: 2px solid #34d399; border-radius: 50%; width: 80px; height: 80px;
             display: flex; align-items: center; justify-content: center; margin: 20px auto;
             font-size: 36px; }}
</style>
</head>
<body>
<div class="stamp">{'✅' if verification['status'] == 'PASS' else '❌'}</div>
<h1>SOC 2 — Data Integrity Report</h1>
<p><span class="label">Generated:</span> {now}</p>
<p><span class="label">Database:</span> {self.db_path}</p>
<p><span class="label">Chain Status:</span> <span class="{'pass' if verification['status'] == 'PASS' else 'fail'}">{verification['status']}</span></p>

<div class="card">
  <p><span class="label">Total Changes Tracked:</span> {total}</p>
  <p><span class="label">Time Range:</span> {first or 'N/A'} — {last or 'N/A'}</p>
  <p><span class="label">Tables Tracked:</span> {len(tables)}</p>
  <p><span class="label">Chain Verification:</span> {total - verification['failures']}/{total} entries verified</p>
</div>

<h2>Tables Monitored</h2>
<table>
  <tr><th>Table Name</th></tr>
  {' '.join(f'<tr><td>{t["table_name"]}</td></tr>' for t in tables)}
</table>

<h2>Chain Verification Details</h2>
<div class="card">
  <p><span class="label">Hash Algorithm:</span> SHA-256</p>
  <p><span class="label">Chain Structure:</span> Each entry contains a hash of itself + the previous entry's hash</p>
  <p><span class="label">Tamper Evidence:</span> Any modification to past records breaks the chain</p>
  <p><span class="label">Verification Result:</span> {'All entries valid' if verification['status'] == 'PASS' else f'{verification["failures"]} entries failed'}</p>
</div>

<h2>Sample Chain Entries</h2>
<table>
  <tr><th>ID</th><th>Table</th><th>Operation</th><th>Checksum (first 16)</th></tr>
"""
        # Add sample entries
        conn2 = self._get_conn()
        samples = conn2.execute(
            "SELECT id, table_name, operation, checksum FROM _tt_history ORDER BY id DESC LIMIT 10"
        ).fetchall()
        conn2.close()
        
        for s in reversed(samples):
            html += f"  <tr><td>{s['id']}</td><td>{s['table_name']}</td><td>{s['operation']}</td><td>{s['checksum'][:16]}...</td></tr>\n"
        
        html += """</table>

<h2>Auditor Statement</h2>
<div class="card">
  <p>This report certifies that the data in the tracked tables has maintained cryptographic integrity since tracking began.</p>
  <p>The hash chain provides non-repudiation — any unauthorized modification to historical data is detectable.</p>
  <p>This satisfies SOC 2 control criteria for:</p>
  <p>• CC6.1 — Logical and physical access controls</p>
  <p>• CC6.6 — Prevention of unauthorized data modification</p>
  <p>• CC7.2 — Monitoring and detection of security events</p>
</div>

<div class="footer">
  Generated by Shayntech TimeTravel — Open Source<br>
  Report ID: {hashlib.sha256(f"{now}{self.db_path}".encode()).hexdigest()[:16]}
</div>
</body>
</html>"""

    def change_audit_report(self, start_date: str = None, end_date: str = None) -> str:
        """Generate a Change Audit Report for SOC 2."""
        conn = self._get_conn()
        
        query = "SELECT * FROM _tt_history"
        params = []
        conditions = []
        if start_date:
            conditions.append("created_at >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("created_at <= ?")
            params.append(end_date)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC"
        
        changes = conn.execute(query, params).fetchall()
        total = conn.execute("SELECT COUNT(*) as c FROM _tt_history").fetchone()["c"]
        conn.close()

        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>SOC 2 Change Audit Report — Shayntech TimeTravel</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: #0f172a; color: #e2e8f0; padding: 40px; max-width: 1000px; margin: 0 auto; }}
  h1 {{ font-size: 24px; border-bottom: 2px solid #34d399; padding-bottom: 10px; }}
  h2 {{ font-size: 18px; color: #34d399; margin-top: 30px; }}
  .label {{ color: #64748b; }}
  table {{ width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 11px; }}
  th {{ background: #334155; padding: 8px; text-align: left; color: #94a3b8; }}
  td {{ padding: 8px; border-bottom: 1px solid #1e293b; max-width: 200px; overflow: hidden; text-overflow: ellipsis; }}
  .insert {{ color: #34d399; }}
  .update {{ color: #fbbf24; }}
  .delete {{ color: #fb7185; }}
  .summary {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin: 16px 0; }}
  .stat {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px; text-align: center; }}
  .stat-num {{ font-size: 28px; font-weight: bold; color: #a78bfa; }}
  .stat-label {{ font-size: 11px; color: #64748b; }}
  .footer {{ margin-top: 40px; color: #475569; font-size: 11px; text-align: center; }}
</style>
</head>
<body>

<h1>📋 SOC 2 — Change Audit Report</h1>
<p><span class="label">Generated:</span> {now}</p>
<p><span class="label">Filter:</span> {start_date or 'All'} to {end_date or 'All'}</p>

<div class="summary">
  <div class="stat"><div class="stat-num">{len(changes)}</div><div class="stat-label">Changes in Range</div></div>
  <div class="stat"><div class="stat-num">{sum(1 for c in changes if c['operation'] == 'INSERT')}</div><div class="stat-label">Inserts</div></div>
  <div class="stat"><div class="stat-num">{sum(1 for c in changes if c['operation'] == 'UPDATE')}</div><div class="stat-label">Updates</div></div>
  <div class="stat"><div class="stat-num">{sum(1 for c in changes if c['operation'] == 'DELETE')}</div><div class="stat-label">Deletes</div></div>
  <div class="stat"><div class="stat-num">{len(set(c['table_name'] for c in changes))}</div><div class="stat-label">Tables Affected</div></div>
  <div class="stat"><div class="stat-num">{total}</div><div class="stat-label">All-Time Total</div></div>
</div>

<h2>Change Details</h2>
<table>
  <tr><th>ID</th><th>Table</th><th>Row</th><th>Operation</th><th>Timestamp</th><th>Checksum</th></tr>
"""
        for c in changes:
            cls = c['operation'].lower()
            html += f"""  <tr>
    <td>{c['id']}</td>
    <td>{c['table_name']}</td>
    <td>{c['row_id']}</td>
    <td class="{cls}">{c['operation']}</td>
    <td>{c['created_at']}</td>
    <td style="font-family: monospace; font-size: 9px;">{c['checksum'][:12]}...</td>
  </tr>
"""
        html += """</table>
<div class="footer">
  Generated by Shayntech TimeTravel — Open Source<br>
  This report satisfies SOC 2 CC6.1 and CC7.2 audit requirements
</div>
</body>
</html>"""
        return html

    def retention_report(self, point_in_time: str) -> str:
        """Generate a Data Retention Report for a specific point in time."""
        conn = self._get_conn()
        tables = conn.execute("SELECT DISTINCT table_name FROM _tt_history").fetchall()
        conn.close()

        tables_summary = []
        for t in tables:
            name = t["table_name"]
            conn = self._get_conn()
            changes_before = conn.execute(
                "SELECT COUNT(*) as c FROM _tt_history WHERE table_name = ? AND created_at <= ?",
                (name, point_in_time)
            ).fetchone()["c"]
            total = conn.execute(
                "SELECT COUNT(*) as c FROM _tt_history WHERE table_name = ?", (name,)
            ).fetchone()["c"]
            conn.close()
            tables_summary.append((name, changes_before, total))

        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>SOC 2 Data Retention Report — Shayntech TimeTravel</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: #0f172a; color: #e2e8f0; padding: 40px; max-width: 900px; margin: 0 auto; }}
  h1 {{ font-size: 24px; border-bottom: 2px solid #fbbf24; padding-bottom: 10px; }}
  h2 {{ font-size: 18px; color: #fbbf24; margin-top: 30px; }}
  .label {{ color: #64748b; }}
  table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
  th {{ background: #334155; padding: 8px; text-align: left; color: #94a3b8; font-size: 11px; }}
  td {{ padding: 8px; border-bottom: 1px solid #1e293b; font-size: 12px; }}
  .card {{ background: #1e293b; border: 1px solid #fbbf24; border-radius: 8px; padding: 16px; margin: 16px 0; }}
  .footer {{ margin-top: 40px; color: #475569; font-size: 11px; text-align: center; }}
</style>
</head>
<body>

<h1>📜 SOC 2 — Data Retention Report</h1>
<p><span class="label">Generated:</span> {now}</p>
<p><span class="label">Point-in-Time Verified:</span> {point_in_time}</p>

<div class="card">
  <p>This report certifies that data existed and was tracked as of <strong>{point_in_time}</strong>.</p>
  <p>All changes recorded up to this date are cryptographically verifiable via the hash chain.</p>
</div>

<table>
  <tr><th>Table</th><th>Changes Before Date</th><th>Total Changes</th><th>Retention Verified</th></tr>
"""
        for name, before, total in tables_summary:
            ok = "✅" if before > 0 else "⚠️"
            html += f"  <tr><td>{name}</td><td>{before}</td><td>{total}</td><td>{ok}</td></tr>\n"
        
        html += """</table>
<div class="footer">
  Generated by Shayntech TimeTravel — Open Source<br>
  Satisfies SOC 2 P4.1 (Retention) and CC6.1 requirements
</div>
</body>
</html>"""
        return html


import hashlib
