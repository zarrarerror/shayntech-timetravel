"""Shayntech TimeTravel — Elite Interactive Dashboard & API Server."""

import json
import os
import sqlite3
import time
from datetime import datetime
from typing import Optional, Any

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from .core import TimeTravelDB, HashChain
from .reports import SOC2Report

# ─── Global config (set once at startup) ────────────────────────────────────
_DB_PATH: Optional[str] = None
_PG_CONN_STR: Optional[str] = None


def _get_chain():
    if _PG_CONN_STR:
        from .pg_adapter import PgHashChain
        return PgHashChain(_PG_CONN_STR)
    return HashChain(_DB_PATH)


def _get_db():
    if _PG_CONN_STR:
        from .pg_adapter import PgTimeTravelDB
        return PgTimeTravelDB(_PG_CONN_STR)
    return TimeTravelDB(_DB_PATH)


def _sqlite(sql: str, params: tuple = ()) -> list[dict]:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _get_tables() -> list[str]:
    if _PG_CONN_STR:
        from .pg_adapter import PgTimeTravelDB
        db = PgTimeTravelDB(_PG_CONN_STR)
        t = db.get_tables()
        db.close()
        return t
    return [r["name"] for r in _sqlite(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE '_tt_%' ORDER BY name"
    )]


# ─── Dashboard HTML ──────────────────────────────────────────────────────────
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Shayntech TimeTravel</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:'Inter',-apple-system,system-ui,sans-serif;background:#07080d;color:#e2e8f0;line-height:1.5;-webkit-font-smoothing:antialiased;overflow-x:hidden}
code,pre,.mono{font-family:'JetBrains Mono',monospace}
:root{
  --brand:#7c3aed;--brand-l:#a78bfa;--brand-d:rgba(124,58,237,.14);
  --green:#10b981;--green-d:rgba(16,185,129,.12);
  --red:#ef4444;--red-d:rgba(239,68,68,.12);
  --yellow:#f59e0b;--yellow-d:rgba(245,158,11,.12);
  --blue:#3b82f6;--blue-d:rgba(59,130,246,.12);
  --t1:#f1f5f9;--t2:#94a3b8;--t3:#64748b;--t4:#475569;
  --bg0:#07080d;--bg1:#0c0e17;--bg2:#11151f;--bg3:#171c28;--bg4:#1e2535;
  --bdr:rgba(255,255,255,.055);--bdr2:rgba(255,255,255,.1);
  --sw:252px;--r:10px;--rs:6px;
}
/* Layout */
.shell{display:flex;min-height:100vh}
/* Sidebar */
.sb{width:var(--sw);background:var(--bg1);border-right:1px solid var(--bdr);display:flex;flex-direction:column;position:fixed;top:0;left:0;bottom:0;z-index:100;transition:transform .3s cubic-bezier(.4,0,.2,1)}
.sb-logo{display:flex;align-items:center;gap:10px;padding:18px 16px 14px;border-bottom:1px solid var(--bdr)}
.sb-mark{width:30px;height:30px;border-radius:8px;background:linear-gradient(135deg,#4f46e5,#7c3aed);display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0}
.sb-name{font-weight:800;font-size:15px;letter-spacing:-.3px}
.sb-name span{color:var(--brand-l)}
.sb-nav{flex:1;padding:8px;overflow-y:auto}
.sb-sec{font-size:10px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:var(--t4);padding:14px 8px 5px}
.nb{display:flex;align-items:center;gap:9px;width:100%;padding:8px 10px;border-radius:var(--rs);font-size:13.5px;font-weight:500;color:var(--t2);background:none;border:none;cursor:pointer;text-align:left;transition:all .15s}
.nb:hover{background:var(--bg2);color:var(--t1)}
.nb.active{background:var(--brand-d);color:var(--brand-l)}
.ni{font-size:14px;flex-shrink:0;opacity:.85}
.sb-tables{padding:8px;border-top:1px solid var(--bdr)}
.sb-ti{display:flex;align-items:center;gap:7px;padding:5px 8px;border-radius:var(--rs);font-size:12.5px;color:var(--t3);cursor:pointer;transition:all .15s}
.sb-ti:hover{background:var(--bg2);color:var(--t2)}
.sb-dot{width:5px;height:5px;border-radius:50%;background:var(--brand);opacity:.7;flex-shrink:0}
.sb-chain{margin:8px;padding:10px 12px;border-radius:var(--rs);background:var(--green-d);border:1px solid rgba(16,185,129,.2)}
.sb-chain .cl{font-size:11px;color:var(--green);font-weight:700}
.sb-chain .cc{font-size:11.5px;color:var(--t3);margin-top:2px}
/* Main */
.main{margin-left:var(--sw);flex:1;display:flex;flex-direction:column;min-width:0}
/* Topbar */
.topbar{display:flex;align-items:center;gap:10px;padding:0 24px;height:52px;border-bottom:1px solid var(--bdr);background:rgba(7,8,13,.88);backdrop-filter:blur(16px);position:sticky;top:0;z-index:50}
.tb-db{display:flex;align-items:center;gap:7px;font-size:13px;color:var(--t2)}
.tb-db .dn{color:var(--t1);font-weight:600;font-family:'JetBrains Mono',monospace;font-size:12px}
.live-dot{width:6px;height:6px;border-radius:50%;background:var(--green);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
.tb-sp{flex:1}
.tb-acts{display:flex;align-items:center;gap:7px}
.btn{display:inline-flex;align-items:center;gap:5px;padding:7px 14px;border-radius:var(--rs);font-size:12.5px;font-weight:500;border:1px solid var(--bdr2);background:var(--bg2);color:var(--t2);cursor:pointer;transition:all .2s;font-family:'Inter',sans-serif}
.btn:hover{background:var(--bg3);color:var(--t1);border-color:rgba(255,255,255,.14)}
.btn.pri{background:var(--brand);border-color:var(--brand);color:#fff}
.btn.pri:hover{background:#6d28d9}
.btn:disabled{opacity:.5;cursor:not-allowed}
/* Content */
.content{flex:1;padding:24px;overflow-y:auto}
.tp{display:none}
.tp.active{display:block;animation:fadeUp .2s ease}
@keyframes fadeUp{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:translateY(0)}}
/* Page header */
.ph{margin-bottom:22px}
.ph h2{font-size:21px;font-weight:700;letter-spacing:-.3px}
.ph p{font-size:13.5px;color:var(--t3);margin-top:3px}
/* Card */
.card{background:var(--bg2);border:1px solid var(--bdr);border-radius:var(--r);padding:18px}
.card+.card{margin-top:14px}
.ct{font-size:11px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;color:var(--t3);margin-bottom:12px}
/* Stats */
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px}
.sc{background:var(--bg2);border:1px solid var(--bdr);border-radius:var(--r);padding:16px}
.sc .sl{font-size:12px;color:var(--t3);margin-bottom:6px}
.sc .sv{font-size:26px;font-weight:700;letter-spacing:-.5px}
.sc .ss{font-size:11.5px;color:var(--t4);margin-top:3px}
.sc.grn .sv{color:var(--green)}
.sc.pur .sv{color:var(--brand-l)}
/* Fields */
.qform{display:grid;grid-template-columns:1fr 1.3fr 1fr auto;gap:9px;align-items:end;margin-bottom:10px}
.fg{display:flex;flex-direction:column;gap:4px}
.fl{font-size:10.5px;font-weight:700;color:var(--t3);letter-spacing:.5px;text-transform:uppercase}
.fi,.fs{padding:8px 11px;border-radius:var(--rs);border:1px solid var(--bdr2);background:var(--bg3);color:var(--t1);font-size:13px;font-family:'Inter',sans-serif;outline:none;transition:border-color .2s,box-shadow .2s}
.fi:focus,.fs:focus{border-color:var(--brand-l);box-shadow:0 0 0 3px rgba(124,58,237,.14)}
.fi::placeholder{color:var(--t4)}
/* Presets */
.presets{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:12px}
.pb{padding:4px 10px;border-radius:100px;font-size:11px;font-weight:500;border:1px solid var(--bdr2);background:var(--bg3);color:var(--t3);cursor:pointer;transition:all .15s}
.pb:hover{background:var(--bg4);color:var(--t2);border-color:rgba(255,255,255,.14)}
/* Format row */
.fmtrow{display:flex;align-items:center;gap:14px;margin-bottom:12px}
.fmtlbl{font-size:12px;color:var(--t3);font-weight:500}
.rg{display:flex;gap:12px}
.ro{display:flex;align-items:center;gap:5px;font-size:13px;color:var(--t2);cursor:pointer}
.ro input[type=radio]{accent-color:var(--brand)}
/* Results */
.rmeta{display:flex;align-items:center;gap:10px;padding:8px 0;margin-bottom:10px;border-bottom:1px solid var(--bdr);font-size:13px;color:var(--t3);flex-wrap:wrap}
.badge{display:inline-flex;align-items:center;padding:2px 9px;border-radius:100px;font-size:11px;font-weight:600}
.bgrn{background:var(--green-d);color:var(--green)}
.byel{background:var(--yellow-d);color:var(--yellow)}
.bred{background:var(--red-d);color:var(--red)}
.bpur{background:var(--brand-d);color:var(--brand-l)}
.bblu{background:var(--blue-d);color:var(--blue)}
.rtw{overflow-x:auto;border-radius:var(--rs)}
.rt{width:100%;border-collapse:collapse;font-size:12.5px}
.rt th{padding:9px 13px;text-align:left;font-size:10.5px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;color:var(--t3);background:var(--bg3);border-bottom:1px solid var(--bdr);cursor:pointer;user-select:none;white-space:nowrap}
.rt th:hover{color:var(--t1)}
.rt th.sa::after{content:' ↑';color:var(--brand-l)}
.rt th.sd::after{content:' ↓';color:var(--brand-l)}
.rt td{padding:9px 13px;border-bottom:1px solid var(--bdr);color:var(--t1);max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rt tr:last-child td{border-bottom:none}
.rt tr:hover td{background:var(--bg3)}
.nv{color:var(--t4);font-style:italic}
.numv{color:#93c5fd;font-family:'JetBrains Mono',monospace;font-size:11.5px}
.ract{display:flex;gap:7px;margin-top:10px;justify-content:flex-end}
.abtn{display:inline-flex;align-items:center;gap:5px;padding:5px 11px;border-radius:var(--rs);font-size:12px;font-weight:500;border:1px solid var(--bdr2);background:var(--bg3);color:var(--t2);cursor:pointer;transition:all .15s;text-decoration:none}
.abtn:hover{background:var(--bg4);color:var(--t1)}
/* JSON */
.jv{background:var(--bg3);border:1px solid var(--bdr);border-radius:var(--rs);padding:14px;font-family:'JetBrains Mono',monospace;font-size:11.5px;color:#93c5fd;overflow:auto;max-height:480px;white-space:pre}
/* Feed */
.fctl{display:flex;align-items:center;gap:10px;margin-bottom:14px}
.fst{font-size:13px;color:var(--t3)}
.fstream{display:flex;flex-direction:column;gap:7px;max-height:520px;overflow-y:auto;padding-right:3px}
.fi2{display:flex;align-items:flex-start;gap:10px;padding:10px 13px;border-radius:var(--rs);background:var(--bg2);border:1px solid var(--bdr);animation:slideIn .3s ease}
@keyframes slideIn{from{opacity:0;transform:translateY(-7px)}to{opacity:1;transform:translateY(0)}}
.fop{flex-shrink:0;width:68px;text-align:center;padding:3px 0;border-radius:var(--rs);font-size:10px;font-weight:700;letter-spacing:.5px}
.fop.INSERT{background:var(--green-d);color:var(--green)}
.fop.UPDATE{background:var(--yellow-d);color:var(--yellow)}
.fop.DELETE{background:var(--red-d);color:var(--red)}
.fop.BASELINE{background:var(--blue-d);color:var(--blue)}
.fnfo{flex:1;min-width:0}
.ftbl{font-size:12.5px;font-weight:600;color:var(--t1)}
.fmeta{font-size:11px;color:var(--t3);margin-top:1px;font-family:'JetBrains Mono',monospace}
.ftime{font-size:10.5px;color:var(--t4);flex-shrink:0}
/* Log */
.logf{display:flex;gap:8px;margin-bottom:14px;align-items:flex-end;flex-wrap:wrap}
.tll{display:flex;flex-direction:column}
.tle{display:flex;gap:14px;padding:13px 0;border-bottom:1px solid var(--bdr)}
.tle:last-child{border-bottom:none}
.tll2{display:flex;flex-direction:column;align-items:center;flex-shrink:0;width:44px}
.tln{font-size:10.5px;font-weight:700;color:var(--t4);font-family:'JetBrains Mono',monospace}
.tlline{flex:1;width:1px;background:var(--bdr);margin:3px 0}
.tlr{flex:1;min-width:0}
.tlh{display:flex;align-items:center;gap:7px;margin-bottom:4px;flex-wrap:wrap}
.tlw{font-size:11px;color:var(--t4);font-family:'JetBrains Mono',monospace}
.tlhash{font-size:10px;color:var(--t4);font-family:'JetBrains Mono',monospace}
.tld{display:none;margin-top:7px}
.tle.exp .tld{display:block}
.tlex{font-size:11px;color:var(--brand-l);cursor:pointer;background:none;border:none;font-family:'Inter',sans-serif}
.dpair{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:5px}
.db2{background:var(--red-d);border-radius:var(--rs);padding:7px;font-size:11px}
.da{background:var(--green-d);border-radius:var(--rs);padding:7px;font-size:11px}
.dlbl{font-size:9.5px;font-weight:700;margin-bottom:3px}
.db2 .dlbl{color:var(--red)}
.da .dlbl{color:var(--green)}
/* Diff */
.dform{display:grid;grid-template-columns:1fr 1fr 1fr auto;gap:9px;align-items:end;margin-bottom:14px}
.dres{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.dpane{background:var(--bg2);border:1px solid var(--bdr);border-radius:var(--r);padding:15px}
.dpane-t{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--t3);margin-bottom:10px}
/* Verify */
.vbanner{display:flex;align-items:center;gap:12px;padding:14px 18px;border-radius:var(--r);margin-bottom:14px}
.vpass{background:var(--green-d);border:1px solid rgba(16,185,129,.25)}
.vfail{background:var(--red-d);border:1px solid rgba(239,68,68,.25)}
.vstats{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:18px}
.vs{background:var(--bg3);border:1px solid var(--bdr);border-radius:var(--rs);padding:13px;text-align:center}
.vsn{font-size:24px;font-weight:700}
.vsl{font-size:11.5px;color:var(--t3);margin-top:2px}
.cviz{overflow-x:auto;padding:10px 0}
.cnodes{display:flex;align-items:center;min-width:max-content}
.cnode{background:var(--bg3);border:1px solid var(--bdr2);border-radius:var(--rs);padding:7px 11px;font-size:10.5px;text-align:center;min-width:96px}
.cnode.ok{border-color:rgba(16,185,129,.3)}
.cnode.bad{border-color:rgba(239,68,68,.3)}
.cid{font-weight:700;color:var(--t1)}
.cop{font-size:9.5px;margin:2px 0}
.chash{font-family:'JetBrains Mono',monospace;font-size:9px;color:var(--t4)}
.carr{color:var(--t4);font-size:14px;padding:0 3px;flex-shrink:0}
/* Reports */
.rgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:18px}
.rcard{background:var(--bg2);border:1px solid var(--bdr);border-radius:var(--r);padding:17px;cursor:pointer;transition:all .2s}
.rcard:hover{border-color:rgba(124,58,237,.35);transform:translateY(-2px)}
.rci{font-size:26px;margin-bottom:9px}
.rct{font-size:14px;font-weight:600;margin-bottom:4px}
.rcd{font-size:12.5px;color:var(--t3)}
.rprev{border:1px solid var(--bdr);border-radius:var(--r);overflow:hidden;margin-top:14px}
.rprev iframe{width:100%;height:520px;border:none}
/* Empty */
.empty{text-align:center;padding:44px 20px;color:var(--t4)}
.eico{font-size:36px;margin-bottom:10px;opacity:.5}
.etxt{font-size:13.5px}
/* Toast */
.tw{position:fixed;bottom:22px;right:22px;display:flex;flex-direction:column;gap:7px;z-index:9999}
.toast{padding:11px 17px;border-radius:var(--rs);font-size:13px;font-weight:500;color:#fff;animation:toastIn .3s ease;box-shadow:0 4px 20px rgba(0,0,0,.45)}
.toast.ok{background:var(--green)}
.toast.err{background:var(--red)}
.toast.inf{background:var(--brand)}
@keyframes toastIn{from{opacity:0;transform:translateY(9px)}to{opacity:1;transform:translateY(0)}}
/* Scrollbar */
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--bg4);border-radius:10px}
::-webkit-scrollbar-thumb:hover{background:var(--t4)}
/* Responsive */
@media(max-width:960px){.stats{grid-template-columns:repeat(2,1fr)}.rgrid{grid-template-columns:repeat(2,1fr)}.qform{grid-template-columns:1fr 1fr}.dform{grid-template-columns:1fr 1fr}.dres{grid-template-columns:1fr}.vstats{grid-template-columns:repeat(2,1fr)}}
@media(max-width:680px){:root{--sw:0px}.sb{transform:translateX(-252px)}.sb.open{transform:translateX(0)}.main{margin-left:0!important}.content{padding:14px}.topbar{padding:0 14px}.rgrid,.stats{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="shell">

<!-- Sidebar -->
<aside class="sb" id="sb">
  <div class="sb-logo">
    <div class="sb-mark">⏮</div>
    <div class="sb-name">Time<span>Travel</span></div>
  </div>
  <nav class="sb-nav">
    <div class="sb-sec">Navigate</div>
    <button class="nb active" data-tab="overview"><span class="ni">📊</span> Overview</button>
    <button class="nb" data-tab="query"><span class="ni">🔮</span> Time Travel Query</button>
    <button class="nb" data-tab="feed"><span class="ni">📡</span> Live Feed</button>
    <button class="nb" data-tab="diff"><span class="ni">↔️</span> Diff</button>
    <button class="nb" data-tab="log"><span class="ni">📝</span> Change Log</button>
    <div class="sb-sec">Compliance</div>
    <button class="nb" data-tab="verify"><span class="ni">🔗</span> Chain Verify</button>
    <button class="nb" data-tab="reports"><span class="ni">📋</span> SOC 2 Reports</button>
  </nav>
  <div class="sb-tables">
    <div class="sb-sec" style="padding-top:6px">Tables</div>
    <div id="sb-tl"><div style="font-size:12px;color:var(--t4);padding:5px 8px">Loading...</div></div>
  </div>
  <div class="sb-chain" id="sb-chain">
    <div class="cl">⬤ Chain Status</div>
    <div class="cc" id="sb-cc">Checking...</div>
  </div>
</aside>

<!-- Main -->
<div class="main" id="main">
  <header class="topbar">
    <button onclick="toggleSb()" style="background:none;border:none;color:var(--t2);font-size:18px;cursor:pointer;padding:4px 6px;line-height:1">☰</button>
    <div class="tb-db">
      <span>🗄️</span><span class="dn" id="tb-db">—</span>
      <div class="live-dot"></div><span style="font-size:12px">Live</span>
    </div>
    <div class="tb-sp"></div>
    <div class="tb-acts">
      <button class="btn" onclick="quickVerify()">🔗 Verify</button>
      <button class="btn pri" onclick="showTab('reports')">📋 Reports</button>
    </div>
  </header>

  <div class="content">

    <!-- OVERVIEW -->
    <div class="tp active" id="tab-overview">
      <div class="ph"><h2>Overview</h2><p>Database status, chain integrity and recent activity.</p></div>
      <div class="stats">
        <div class="sc"><div class="sl">Tables Tracked</div><div class="sv" id="st-tbl">—</div><div class="ss">in this database</div></div>
        <div class="sc pur"><div class="sl">Total Changes</div><div class="sv" id="st-tot">—</div><div class="ss">entries recorded</div></div>
        <div class="sc grn"><div class="sl">Chain Integrity</div><div class="sv" id="st-chain">—</div><div class="ss" id="st-chain-s">—</div></div>
        <div class="sc"><div class="sl">Latest Entry</div><div class="sv" style="font-size:13px;font-family:'JetBrains Mono',monospace" id="st-lat">—</div><div class="ss" id="st-lat-s">—</div></div>
      </div>
      <div class="card">
        <div class="ct">Recent Changes</div>
        <div id="ov-recent"><div style="color:var(--t4);font-size:13px">Loading...</div></div>
      </div>
    </div>

    <!-- QUERY -->
    <div class="tp" id="tab-query">
      <div class="ph">
        <h2>Time Travel Query</h2>
        <p>Reconstruct your database at any point in the past. Press <kbd style="background:var(--bg3);padding:2px 6px;border-radius:4px;font-size:11px;border:1px solid var(--bdr2)">Ctrl+Enter</kbd> to execute.</p>
      </div>
      <div class="card">
        <div class="qform">
          <div class="fg"><label class="fl">Table</label>
            <select class="fs" id="q-tbl"><option value="">Select table...</option></select></div>
          <div class="fg"><label class="fl">Point in Time</label>
            <input type="datetime-local" class="fi" id="q-at"></div>
          <div class="fg"><label class="fl">Row ID (optional)</label>
            <input type="text" class="fi" id="q-row" placeholder="e.g. 42"></div>
          <div class="fg"><label class="fl">&nbsp;</label>
            <button class="btn pri" id="q-btn" onclick="runQuery()" style="height:37px;padding:0 18px;white-space:nowrap">▶ Execute</button></div>
        </div>
        <div class="presets">
          <span style="font-size:11.5px;color:var(--t4)">Jump to:</span>
          <button class="pb" onclick="setPreset(1,'h')">1 hr ago</button>
          <button class="pb" onclick="setPreset(6,'h')">6 hrs ago</button>
          <button class="pb" onclick="setPreset(1,'d')">Yesterday</button>
          <button class="pb" onclick="setPreset(7,'d')">1 week ago</button>
          <button class="pb" onclick="setPreset(30,'d')">1 month ago</button>
          <button class="pb" onclick="setPreset(365,'d')">1 year ago</button>
        </div>
        <div class="fmtrow">
          <span class="fmtlbl">Output:</span>
          <div class="rg">
            <label class="ro"><input type="radio" name="qfmt" value="table" checked> Table</label>
            <label class="ro"><input type="radio" name="qfmt" value="json"> JSON</label>
          </div>
        </div>
      </div>
      <div id="q-res" style="margin-top:14px"></div>
    </div>

    <!-- LIVE FEED -->
    <div class="tp" id="tab-feed">
      <div class="ph"><h2>Live Feed</h2><p>Real-time stream of all database changes as they happen.</p></div>
      <div class="card">
        <div class="fctl">
          <button class="btn" id="feed-btn" onclick="toggleFeed()">⏸ Pause</button>
          <button class="btn" onclick="clearFeed()">🗑 Clear</button>
          <span class="fst" id="feed-st" style="color:var(--green)">● Streaming...</span>
        </div>
        <div class="fstream" id="fstream">
          <div class="empty"><div class="eico">📡</div><div class="etxt">Waiting for changes...</div></div>
        </div>
      </div>
    </div>

    <!-- DIFF -->
    <div class="tp" id="tab-diff">
      <div class="ph"><h2>Diff</h2><p>Compare your data between two points in time, side by side.</p></div>
      <div class="card">
        <div class="dform">
          <div class="fg"><label class="fl">Table</label><select class="fs" id="d-tbl"></select></div>
          <div class="fg"><label class="fl">From</label><input type="datetime-local" class="fi" id="d-from"></div>
          <div class="fg"><label class="fl">To</label><input type="datetime-local" class="fi" id="d-to"></div>
          <div class="fg"><label class="fl">&nbsp;</label><button class="btn pri" onclick="runDiff()" style="height:37px">↔ Compare</button></div>
        </div>
      </div>
      <div id="diff-res" style="margin-top:14px"></div>
    </div>

    <!-- LOG -->
    <div class="tp" id="tab-log">
      <div class="ph"><h2>Change Log</h2><p>Full history of every change, with before/after data diffs.</p></div>
      <div class="card">
        <div class="logf">
          <div class="fg"><label class="fl">Table</label><select class="fs" id="l-tbl" style="min-width:140px"></select></div>
          <div class="fg"><label class="fl">Row ID (optional)</label><input type="text" class="fi" id="l-row" placeholder="e.g. 42" style="width:120px"></div>
          <div class="fg"><label class="fl">Limit</label>
            <select class="fs" id="l-lim" style="width:85px">
              <option value="25">25</option><option value="50" selected>50</option><option value="100">100</option><option value="500">500</option>
            </select></div>
          <div class="fg"><label class="fl">&nbsp;</label><button class="btn pri" onclick="runLog()" style="height:37px">Load Log</button></div>
        </div>
      </div>
      <div id="log-res" style="margin-top:14px"></div>
    </div>

    <!-- VERIFY -->
    <div class="tp" id="tab-verify">
      <div class="ph"><h2>Chain Verification</h2><p>Cryptographically verify every entry in the change chain for tampering.</p></div>
      <div id="ver-res">
        <div class="card" style="text-align:center;padding:40px">
          <div style="font-size:38px;margin-bottom:10px">🔗</div>
          <div style="color:var(--t3);font-size:13.5px;margin-bottom:16px">Scan all chain entries and verify SHA-256 integrity.</div>
          <button class="btn pri" onclick="runVerify()" style="padding:10px 28px;font-size:13.5px">🔍 Verify Chain</button>
        </div>
      </div>
    </div>

    <!-- REPORTS -->
    <div class="tp" id="tab-reports">
      <div class="ph"><h2>SOC 2 Reports</h2><p>Generate compliance evidence for auditors — click any report to preview and download.</p></div>
      <div class="rgrid">
        <div class="rcard" onclick="genReport('integrity')">
          <div class="rci">🛡️</div>
          <div class="rct">Integrity Report</div>
          <div class="rcd">Hash chain proof of tamper-evident data. Satisfies CC6.1, CC6.6, CC7.2.</div>
        </div>
        <div class="rcard" onclick="genReport('audit')">
          <div class="rci">📋</div>
          <div class="rct">Change Audit Report</div>
          <div class="rcd">All operations grouped by table with full change details.</div>
        </div>
        <div class="rcard" onclick="genReport('retention')">
          <div class="rci">📜</div>
          <div class="rct">Retention Report</div>
          <div class="rcd">Proves data existed at a point in time. Satisfies P4.1.</div>
        </div>
      </div>
      <div id="rprev" style="display:none">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
          <span style="font-size:13.5px;font-weight:600;color:var(--t2)" id="rprev-t">Report Preview</span>
          <div style="display:flex;gap:7px">
            <a class="abtn" id="rdl" download style="text-decoration:none">📥 Download</a>
            <button class="abtn" onclick="document.getElementById('rprev').style.display='none'">✕ Close</button>
          </div>
        </div>
        <div class="rprev"><iframe id="riframe" title="Report"></iframe></div>
      </div>
    </div>

  </div><!-- /content -->
</div><!-- /main -->
</div><!-- /shell -->

<div class="tw" id="tw"></div>

<script>
// ─── State ───────────────────────────────────────────────────────────────────
let _tables = [], _feedOn = true, _lastFeedId = 0, _feedInterval = null;
let _sortCol = null, _sortDir = 1, _qdata = [];

// ─── Boot ────────────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', async () => {
  await loadStatus();
  fillDropdowns();
  setDefaultTimes();
  startFeed();
  loadRecentActivity();
});

async function loadStatus() {
  try {
    const d = await api('/api/status');
    _tables = d.tables || [];
    document.getElementById('tb-db').textContent = d.db_name || '—';
    document.getElementById('st-tbl').textContent = _tables.length;
    document.getElementById('st-tot').textContent = (d.total_entries || 0).toLocaleString();
    const ok = d.chain_ok;
    document.getElementById('st-chain').textContent = ok ? '✓ PASS' : '✗ FAIL';
    document.getElementById('st-chain').style.color = ok ? 'var(--green)' : 'var(--red)';
    document.getElementById('st-chain-s').textContent = (d.total_entries || 0) + ' entries';
    if (!ok) {
      const c = document.getElementById('sb-chain');
      c.style.background = 'var(--red-d)';
      c.style.borderColor = 'rgba(239,68,68,.2)';
      c.querySelector('.cl').style.color = 'var(--red)';
    }
    document.getElementById('sb-cc').textContent = (d.total_entries || 0) + ' entries · ' + (ok ? 'PASS' : 'FAIL');
    if (d.latest_entry) {
      const e = d.latest_entry;
      document.getElementById('st-lat').textContent = (e.created_at || '').slice(0,16);
      document.getElementById('st-lat-s').textContent = (e.operation||'') + ' on ' + (e.table_name||'');
    }
    const sbTl = document.getElementById('sb-tl');
    sbTl.innerHTML = _tables.map(t =>
      `<div class="sb-ti" onclick="quickQuery('${t}')"><div class="sb-dot"></div>${t}</div>`
    ).join('') || '<div style="font-size:12px;color:var(--t4);padding:5px 8px">No tables found</div>';
  } catch(e) { toast('API connection failed', 'err'); }
}

function fillDropdowns() {
  ['q-tbl','d-tbl','l-tbl'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = '<option value="">Select table...</option>' + _tables.map(t=>`<option value="${t}">${t}</option>`).join('');
  });
}

function setDefaultTimes() {
  const now = new Date(), week = new Date(now - 7*864e5);
  const fmt = d => d.toISOString().slice(0,16);
  document.getElementById('q-at').value = fmt(week);
  document.getElementById('d-from').value = fmt(week);
  document.getElementById('d-to').value = fmt(now);
}

// ─── Navigation ───────────────────────────────────────────────────────────────
function showTab(name) {
  document.querySelectorAll('.tp').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nb').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-'+name)?.classList.add('active');
  document.querySelector(`[data-tab="${name}"]`)?.classList.add('active');
}
document.querySelectorAll('.nb[data-tab]').forEach(b => b.addEventListener('click', () => showTab(b.dataset.tab)));

function toggleSb() { document.getElementById('sb').classList.toggle('open'); }

// ─── Query ────────────────────────────────────────────────────────────────────
async function runQuery() {
  const table = document.getElementById('q-tbl').value;
  const at    = document.getElementById('q-at').value;
  const row   = document.getElementById('q-row').value;
  const fmt   = document.querySelector('input[name="qfmt"]:checked')?.value || 'table';
  if (!table) { toast('Select a table', 'err'); return; }
  if (!at)    { toast('Choose a point in time', 'err'); return; }
  const btn = document.getElementById('q-btn');
  btn.textContent = '⏳ Running...'; btn.disabled = true;
  const t0 = Date.now();
  try {
    const d = await api('/api/query', {method:'POST', body:{table, at:at.replace('T',' '), row_id:row||null}});
    const ms = Date.now() - t0;
    _qdata = d.rows || [];
    _sortCol = null;
    renderQuery(_qdata, table, at, ms, fmt);
  } catch(e) { toast('Query error: '+e.message,'err'); }
  finally { btn.textContent = '▶ Execute'; btn.disabled = false; }
}

function renderQuery(rows, table, at, ms, fmt) {
  const el = document.getElementById('q-res');
  if (!rows.length) {
    el.innerHTML = `<div class="card"><div class="empty"><div class="eico">🔍</div><div class="etxt">No data at this point in time.</div></div></div>`;
    return;
  }
  if (fmt === 'json') {
    el.innerHTML = `<div class="card">
      <div class="rmeta"><span class="badge bpur">${rows.length} rows</span><span>Table: <b>${table}</b></span><span>At: <b>${at}</b></span><span>${ms}ms</span></div>
      <div class="jv">${JSON.stringify(rows,null,2)}</div>
      <div class="ract"><button class="abtn" onclick="copyJSON()">📋 Copy JSON</button></div>
    </div>`; return;
  }
  const cols = Object.keys(rows[0]);
  const thead = cols.map(c=>`<th id="th-${c}" onclick="sortQ('${c}')">${c}</th>`).join('');
  const tbody = rows.map(r=>`<tr>${cols.map(c=>{
    const v=r[c];
    if(v===null||v===undefined) return`<td><span class="nv">NULL</span></td>`;
    if(typeof v==='number') return`<td><span class="numv">${v}</span></td>`;
    const s=String(v); return`<td title="${s.replace(/"/g,'&quot;')}">${s.length>60?s.slice(0,60)+'…':s}</td>`;
  }).join('')}</tr>`).join('');
  el.innerHTML = `<div class="card">
    <div class="rmeta"><span class="badge bpur">${rows.length} rows</span><span>Table: <b>${table}</b></span><span>At: <b>${at}</b></span><span>${ms}ms</span></div>
    <div class="rtw"><table class="rt" id="rtbl"><thead><tr>${thead}</tr></thead><tbody>${tbody}</tbody></table></div>
    <div class="ract">
      <button class="abtn" onclick="copyJSON()">📋 Copy JSON</button>
      <button class="abtn" onclick="dlCSV('${table}')">📥 CSV</button>
    </div>
  </div>`;
}

function sortQ(col) {
  if (_sortCol===col) _sortDir*=-1; else { _sortCol=col; _sortDir=1; }
  document.querySelectorAll('.rt th').forEach(t=>t.classList.remove('sa','sd'));
  const th=document.getElementById('th-'+col);
  if(th) th.classList.add(_sortDir===1?'sa':'sd');
  const s=[..._qdata].sort((a,b)=>{
    const va=a[col],vb=b[col];
    if(va===null) return 1; if(vb===null) return -1;
    return va<vb?-_sortDir:va>vb?_sortDir:0;
  });
  const fmt=document.querySelector('input[name="qfmt"]:checked')?.value||'table';
  renderQuery(s,document.getElementById('q-tbl').value,document.getElementById('q-at').value,0,fmt);
  _qdata=s;
}

function setPreset(n, unit) {
  const ms = unit==='h' ? n*3600000 : n*86400000;
  document.getElementById('q-at').value = new Date(Date.now()-ms).toISOString().slice(0,16);
}

function quickQuery(table) {
  showTab('query');
  document.getElementById('q-tbl').value = table;
  setPreset(7,'d');
  runQuery();
}

function copyJSON() {
  navigator.clipboard?.writeText(JSON.stringify(_qdata,null,2));
  toast('Copied to clipboard','ok');
}

function dlCSV(table) {
  if(!_qdata.length) return;
  const cols=Object.keys(_qdata[0]);
  const lines=[cols.join(','),..._qdata.map(r=>cols.map(c=>JSON.stringify(r[c]??'')).join(','))];
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([lines.join('\\n')],{type:'text/csv'}));
  a.download=table+'_timetravel.csv'; a.click();
  toast('CSV downloaded','ok');
}

document.addEventListener('keydown', e => {
  if ((e.ctrlKey||e.metaKey) && e.key==='Enter') {
    if (document.getElementById('tab-query').classList.contains('active')) runQuery();
  }
});

// ─── Live Feed ────────────────────────────────────────────────────────────────
function startFeed() {
  if(_feedInterval) clearInterval(_feedInterval);
  _feedInterval = setInterval(pollFeed, 2200);
  pollFeed();
}

async function pollFeed() {
  if(!_feedOn) return;
  try {
    const d = await api(`/api/feed?since_id=${_lastFeedId}`);
    if (d.entries?.length) {
      const s = document.getElementById('fstream');
      if(s.querySelector('.empty')) s.innerHTML='';
      for(const e of [...d.entries].reverse()) {
        _lastFeedId = Math.max(_lastFeedId, e.id);
        const div = document.createElement('div');
        div.className='fi2';
        div.innerHTML=`<div class="fop ${e.operation}">${e.operation}</div>
          <div class="fnfo"><div class="ftbl">${e.table_name} <span style="font-weight:400;color:var(--t3)">row ${e.row_id}</span></div>
          <div class="fmeta">${(e.checksum||'').slice(0,22)}…</div></div>
          <div class="ftime">${(e.created_at||'').slice(11,19)}</div>`;
        s.insertBefore(div,s.firstChild);
      }
      while(s.children.length>100) s.removeChild(s.lastChild);
    }
    document.getElementById('feed-st').textContent='● Live — '+new Date().toLocaleTimeString();
    document.getElementById('feed-st').style.color='var(--green)';
  } catch(_){}
}

function toggleFeed() {
  _feedOn=!_feedOn;
  document.getElementById('feed-btn').textContent=_feedOn?'⏸ Pause':'▶ Resume';
  document.getElementById('feed-st').textContent=_feedOn?'● Streaming...':'⏸ Paused';
  document.getElementById('feed-st').style.color=_feedOn?'var(--green)':'var(--t4)';
}

function clearFeed() {
  document.getElementById('fstream').innerHTML=`<div class="empty"><div class="eico">📡</div><div class="etxt">Waiting for changes...</div></div>`;
}

// ─── Diff ─────────────────────────────────────────────────────────────────────
async function runDiff() {
  const table=document.getElementById('d-tbl').value;
  const from=document.getElementById('d-from').value;
  const to=document.getElementById('d-to').value;
  if(!table||!from||!to){toast('Fill in all fields','err');return;}
  try {
    const d=await api('/api/diff',{method:'POST',body:{table,from_date:from.replace('T',' '),to_date:to.replace('T',' ')}});
    const el=document.getElementById('diff-res');
    el.innerHTML=`
      <div style="display:flex;gap:10px;margin-bottom:12px;flex-wrap:wrap">
        <span class="badge bred">− ${d.removed} removed</span>
        <span class="badge bgrn">+ ${d.added} added</span>
        <span class="badge bpur">${d.before_count} → ${d.after_count} rows</span>
      </div>
      <div class="dres">
        <div class="dpane"><div class="dpane-t">⬅ Before (${from.slice(0,10)})</div>${miniTable(d.before)}</div>
        <div class="dpane"><div class="dpane-t">➡ After (${to.slice(0,10)})</div>${miniTable(d.after)}</div>
      </div>`;
  } catch(e){toast('Diff failed: '+e.message,'err');}
}

function miniTable(rows) {
  if(!rows?.length) return '<div style="color:var(--t4);font-size:13px;text-align:center;padding:18px">No data</div>';
  const cols=Object.keys(rows[0]);
  const h=cols.map(c=>`<th>${c}</th>`).join('');
  const b=rows.slice(0,25).map(r=>`<tr>${cols.map(c=>{
    const v=r[c];
    if(v===null) return`<td><span class="nv">NULL</span></td>`;
    if(typeof v==='number') return`<td><span class="numv">${v}</span></td>`;
    const s=String(v); return`<td>${s.length>35?s.slice(0,35)+'…':s}</td>`;
  }).join('')}</tr>`).join('');
  const more=rows.length>25?`<tr><td colspan="${cols.length}" style="text-align:center;color:var(--t4);font-size:11.5px">+${rows.length-25} more</td></tr>`:'';
  return `<div style="overflow-x:auto"><table class="rt"><thead><tr>${h}</tr></thead><tbody>${b}${more}</tbody></table></div>`;
}

// ─── Log ──────────────────────────────────────────────────────────────────────
async function runLog() {
  const table=document.getElementById('l-tbl').value;
  const row=document.getElementById('l-row').value;
  const lim=document.getElementById('l-lim').value;
  if(!table){toast('Select a table','err');return;}
  try {
    const p=new URLSearchParams({table,limit:lim});
    if(row) p.set('row_id',row);
    const d=await api('/api/log?'+p);
    const el=document.getElementById('log-res');
    if(!d.entries?.length){
      el.innerHTML=`<div class="card"><div class="empty"><div class="eico">📝</div><div class="etxt">No history found.</div></div></div>`;
      return;
    }
    const items=d.entries.map((e,i)=>{
      const opBadge=`<span class="badge ${opCls(e.operation)}">${e.operation}</span>`;
      let old={},nw={};
      try{ if(e.old_data) old=JSON.parse(e.old_data); }catch(_){}
      try{ if(e.new_data) nw=JSON.parse(e.new_data); }catch(_){}
      const hasData=Object.keys(old).length||Object.keys(nw).length;
      const diffHtml=hasData?`<div class="dpair">
        ${Object.keys(old).length?`<div class="db2"><div class="dlbl">BEFORE</div><pre style="font-size:10.5px;white-space:pre-wrap;color:var(--t2)">${JSON.stringify(old,null,2)}</pre></div>`:'<div></div>'}
        ${Object.keys(nw).length?`<div class="da"><div class="dlbl">AFTER</div><pre style="font-size:10.5px;white-space:pre-wrap;color:var(--t2)">${JSON.stringify(nw,null,2)}</pre></div>`:'<div></div>'}
      </div>`:'' ;
      return `<div class="tle" id="tl${i}">
        <div class="tll2"><div class="tln">#${e.id}</div><div class="tlline"></div></div>
        <div class="tlr">
          <div class="tlh">
            ${opBadge}
            <span class="tlw">${e.created_at||''}</span>
            <span style="font-size:12px;color:var(--t3)">row ${e.row_id}</span>
            ${hasData?`<button class="tlex" onclick="tlToggle(${i})">▼ details</button>`:''}
          </div>
          <div class="tlhash mono">${(e.checksum||'').slice(0,32)}…</div>
          ${hasData?`<div class="tld" id="tld${i}">${diffHtml}</div>`:''}
        </div>
      </div>`;
    }).join('');
    el.innerHTML=`<div class="card"><div class="tll">${items}</div></div>`;
  } catch(e){toast('Log error: '+e.message,'err');}
}

function tlToggle(i){
  const e=document.getElementById('tl'+i);
  const b=e.querySelector('.tlex');
  e.classList.toggle('exp');
  if(b) b.textContent=e.classList.contains('exp')?'▲ hide':'▼ details';
}

function opCls(op){return{INSERT:'bgrn',UPDATE:'byel',DELETE:'bred',BASELINE:'bblu'}[op]||'bpur';}

// ─── Verify ───────────────────────────────────────────────────────────────────
async function runVerify() {
  const el=document.getElementById('ver-res');
  el.innerHTML=`<div class="card" style="text-align:center;padding:40px">
    <div style="font-size:32px;margin-bottom:10px;animation:pulse 1s infinite">🔍</div>
    <div style="color:var(--t3);font-size:13.5px">Scanning chain entries...</div>
  </div>`;
  try {
    const d=await api('/api/verify');
    const pass=d.status==='PASS';
    const bCls=pass?'vbanner vpass':'vbanner vfail';
    const ico=pass?'✅':'❌';
    const col=pass?'var(--green)':'var(--red)';
    let viz='';
    if(d.sample_entries?.length){
      const nodes=d.sample_entries.map(e=>{
        const oc={INSERT:'var(--green)',UPDATE:'var(--yellow)',DELETE:'var(--red)',BASELINE:'var(--blue)'}[e.operation]||'var(--brand-l)';
        return`<div class="cnode ok"><div class="cid">#${e.id}</div><div class="cop" style="color:${oc}">${e.operation}</div><div class="chash">${(e.checksum||'').slice(0,10)}…</div></div>`;
      }).join('<div class="carr">→</div>');
      viz=`<div class="card"><div class="ct">Chain Sample</div><div class="cviz"><div class="cnodes">${nodes}</div></div></div>`;
    }
    el.innerHTML=`
      <div class="${bCls}">
        <span style="font-size:26px">${ico}</span>
        <div><div style="font-weight:700;color:${col};font-size:15px">Verification ${d.status}</div>
        <div style="font-size:12.5px;color:var(--t3)">${pass?'All entries verified — no tampering detected.':d.failures+' entries failed.'}</div></div>
      </div>
      <div class="vstats">
        <div class="vs"><div class="vsn">${d.total}</div><div class="vsl">Total Entries</div></div>
        <div class="vs"><div class="vsn" style="color:var(--green)">${d.total-d.failures}</div><div class="vsl">Verified</div></div>
        <div class="vs"><div class="vsn" style="color:${d.failures>0?'var(--red)':'var(--green)'}">${d.failures}</div><div class="vsl">Failures</div></div>
      </div>
      ${viz}
      <div style="margin-top:14px;text-align:center">
        <button class="btn" onclick="runVerify()" style="padding:9px 26px">🔄 Re-verify</button>
      </div>`;
  } catch(e){toast('Verify error: '+e.message,'err');}
}

async function quickVerify() {
  try {
    const d=await api('/api/verify');
    toast(d.status==='PASS'?`✅ Chain OK — ${d.total} entries verified`:`❌ Chain FAILED — ${d.failures} issues`,d.status==='PASS'?'ok':'err');
  } catch(_){}
}

// ─── Reports ──────────────────────────────────────────────────────────────────
async function genReport(type) {
  toast('Generating '+type+' report...','inf');
  try {
    const r=await fetch('/api/report/'+type);
    if(!r.ok) throw new Error(await r.text());
    const html=await r.text();
    const url=URL.createObjectURL(new Blob([html],{type:'text/html'}));
    document.getElementById('rprev').style.display='block';
    document.getElementById('riframe').src=url;
    document.getElementById('rprev-t').textContent=type[0].toUpperCase()+type.slice(1)+' Report Preview';
    const dl=document.getElementById('rdl');
    dl.href=url; dl.download='soc2-'+type+'-report.html';
    document.getElementById('rprev').scrollIntoView({behavior:'smooth',block:'start'});
    toast('Report ready','ok');
  } catch(e){toast('Report failed: '+e.message,'err');}
}

// ─── Overview Recent ──────────────────────────────────────────────────────────
async function loadRecentActivity() {
  try {
    const d=await api('/api/log?table=_all&limit=10');
    const el=document.getElementById('ov-recent');
    if(!d.entries?.length){
      el.innerHTML='<div style="color:var(--t4);font-size:13px">No history yet — run <code style="background:var(--bg3);padding:1px 6px;border-radius:3px">timetravel init</code> to begin tracking.</div>';
      return;
    }
    const colors={INSERT:'var(--green)',UPDATE:'var(--yellow)',DELETE:'var(--red)',BASELINE:'var(--blue)'};
    el.innerHTML=d.entries.map(e=>`
      <div style="display:flex;align-items:center;gap:9px;padding:7px 0;border-bottom:1px solid var(--bdr)">
        <span style="color:${colors[e.operation]||'var(--brand-l)'};font-weight:700;font-size:11px;width:65px;flex-shrink:0">${e.operation}</span>
        <span style="font-size:13px;color:var(--t2);flex:1">${e.table_name} · row ${e.row_id}</span>
        <span style="font-size:11px;color:var(--t4);font-family:'JetBrains Mono',monospace">${(e.created_at||'').slice(0,19)}</span>
      </div>`).join('');
  } catch(_){}
}

// ─── API helper ───────────────────────────────────────────────────────────────
async function api(url, opts={}) {
  const options = {headers:{}};
  if(opts.method) options.method=opts.method;
  if(opts.body) { options.body=JSON.stringify(opts.body); options.headers['Content-Type']='application/json'; }
  const r=await fetch(url,options);
  if(!r.ok) { const t=await r.text(); throw new Error(t); }
  return r.json();
}

// ─── Toast ────────────────────────────────────────────────────────────────────
function toast(msg,type='inf') {
  const el=document.createElement('div');
  el.className='toast '+type; el.textContent=msg;
  document.getElementById('tw').appendChild(el);
  setTimeout(()=>el.remove(),3500);
}
</script>
</body>
</html>"""


# ─── FastAPI app factory ─────────────────────────────────────────────────────
def create_app(db_path: str = None, pg_conn_str: str = None):
    global _DB_PATH, _PG_CONN_STR
    _DB_PATH = db_path
    _PG_CONN_STR = pg_conn_str

    if not HAS_FASTAPI:
        raise ImportError(
            "FastAPI and uvicorn are required.\n"
            "Install: pip install fastapi uvicorn"
        )

    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, JSONResponse

    app = FastAPI(title="Shayntech TimeTravel", version="0.2.0", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return DASHBOARD_HTML

    @app.get("/api/status")
    async def api_status():
        try:
            tables = _get_tables()
            chain = _get_chain()
            verify = chain.verify_chain()
            db_name = (
                os.path.basename(_DB_PATH) if _DB_PATH
                else (_PG_CONN_STR.split("/")[-1] if _PG_CONN_STR else "Unknown")
            )
            latest = None
            if _DB_PATH:
                rows = _sqlite("SELECT * FROM _tt_history ORDER BY id DESC LIMIT 1")
                latest = rows[0] if rows else None
            return JSONResponse({
                "db_name": db_name,
                "tables": tables,
                "total_entries": verify.get("total", 0),
                "chain_ok": verify.get("status") == "PASS",
                "latest_entry": latest,
            })
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.post("/api/query")
    async def api_query(request: Request):
        try:
            body = await request.json()
            db = _get_db()
            rows = db.query_at(body["at"], body["table"], body.get("row_id"))
            db.close()
            return JSONResponse({"rows": rows})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    @app.get("/api/log")
    async def api_log(table: str = "", row_id: str = None, limit: int = 50):
        try:
            if _DB_PATH:
                if table == "_all":
                    entries = _sqlite("SELECT * FROM _tt_history ORDER BY id DESC LIMIT ?", (limit,))
                elif row_id:
                    entries = _sqlite(
                        "SELECT * FROM _tt_history WHERE table_name=? AND row_id=? ORDER BY id DESC LIMIT ?",
                        (table, row_id, limit)
                    )
                else:
                    entries = _sqlite(
                        "SELECT * FROM _tt_history WHERE table_name=? ORDER BY id DESC LIMIT ?",
                        (table, limit)
                    )
            else:
                from .pg_adapter import _connect, _dict_row
                conn = _connect(_PG_CONN_STR)
                cur = _dict_row(conn)
                if row_id:
                    cur.execute("SELECT * FROM _tt_history WHERE table_name=%s AND row_id=%s ORDER BY id DESC LIMIT %s",
                                (table, row_id, limit))
                else:
                    cur.execute("SELECT * FROM _tt_history WHERE table_name=%s ORDER BY id DESC LIMIT %s",
                                (table, limit))
                entries = [dict(r) for r in cur.fetchall()]
                conn.close()
            return JSONResponse({"entries": entries})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    @app.get("/api/feed")
    async def api_feed(since_id: int = 0):
        try:
            if _DB_PATH:
                entries = _sqlite(
                    "SELECT * FROM _tt_history WHERE id > ? ORDER BY id ASC LIMIT 50",
                    (since_id,)
                )
            else:
                from .pg_adapter import _connect, _dict_row
                conn = _connect(_PG_CONN_STR)
                cur = _dict_row(conn)
                cur.execute("SELECT * FROM _tt_history WHERE id > %s ORDER BY id ASC LIMIT 50", (since_id,))
                entries = [dict(r) for r in cur.fetchall()]
                conn.close()
            return JSONResponse({"entries": entries})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.get("/api/verify")
    async def api_verify():
        try:
            chain = _get_chain()
            result = chain.verify_chain()
            samples: list[dict] = []
            if _DB_PATH:
                samples = _sqlite(
                    "SELECT id, table_name, operation, checksum, created_at FROM _tt_history ORDER BY id LIMIT 12"
                )
            result["sample_entries"] = samples
            return JSONResponse(result)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.post("/api/diff")
    async def api_diff(request: Request):
        try:
            body = await request.json()
            table = body["table"]
            from_date = body["from_date"]
            to_date = body["to_date"]
            db = _get_db()
            before = db.query_at(from_date, table)
            after = db.query_at(to_date, table)
            db.close()

            def row_key(r: dict) -> str:
                for k in ("id", "rowid"):
                    if k in r:
                        return str(r[k])
                return str(list(r.values())[0]) if r else ""

            before_ids = {row_key(r) for r in before}
            after_ids = {row_key(r) for r in after}
            return JSONResponse({
                "before": before,
                "after": after,
                "before_count": len(before),
                "after_count": len(after),
                "added": len(after_ids - before_ids),
                "removed": len(before_ids - after_ids),
            })
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    @app.get("/api/report/{report_type}")
    async def api_report(report_type: str):
        try:
            from fastapi.responses import HTMLResponse as HR
            if not _DB_PATH:
                return JSONResponse({"error": "Reports require SQLite mode in this version"}, status_code=400)
            report = SOC2Report(_DB_PATH)
            if report_type == "integrity":
                html = report.integrity_report()
            elif report_type == "audit":
                html = report.change_audit_report()
            elif report_type == "retention":
                html = report.retention_report(datetime.utcnow().strftime("%Y-%m-%d"))
            else:
                return JSONResponse({"error": "Unknown report type"}, status_code=400)
            return HR(html)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    return app


# ─── Entry point ─────────────────────────────────────────────────────────────
def serve(
    db_path: str = None,
    pg_conn_str: str = None,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
):
    """Start the TimeTravel dashboard server."""
    if not HAS_FASTAPI:
        raise ImportError("Install: pip install fastapi uvicorn")

    import uvicorn

    app = create_app(db_path, pg_conn_str)
    db_label = os.path.basename(db_path) if db_path else "PostgreSQL"

    print(f"\n{'─'*52}")
    print(f"  ⏮  SHAYNTECH TIMETRAVEL — DASHBOARD")
    print(f"{'─'*52}")
    print(f"  Database : {db_label}")
    print(f"  URL      : http://{host}:{port}")
    print(f"  Press Ctrl+C to stop")
    print(f"{'─'*52}\n")

    if open_browser:
        import threading
        import webbrowser
        def _open():
            time.sleep(1.3)
            webbrowser.open(f"http://{host}:{port}")
        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run(app, host=host, port=port, log_level="warning")
