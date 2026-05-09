# ⏮ Shayntech TimeTravel

> **Accidentally deleted production data? Get it back in seconds.**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![Works with PostgreSQL](https://img.shields.io/badge/PostgreSQL-supported-blue?logo=postgresql)](https://postgresql.org)
[![Works with NeonDB](https://img.shields.io/badge/NeonDB-supported-green)](https://neon.tech)

<p align="center">
  <img src="Animation.gif" alt="Shayntech TimeTravel Demo" width="100%">
</p>

**Shayntech TimeTravel** gives any PostgreSQL or SQLite database a complete time machine — query your data at any point in the past, restore deleted rows with one click, and generate SOC 2 audit reports automatically.

No cloud dependency. No vendor lock-in. Fully open source.

---

## ✨ What It Does

| Feature | Description |
|---|---|
| 🔮 **Time Travel Query** | Reconstruct your exact database state at any timestamp |
| 🔄 **One-Click Restore** | Recover deleted rows instantly from the dashboard |
| 📡 **Auto-Capture Triggers** | Tracks every INSERT/UPDATE/DELETE — even direct DB edits |
| ↔️ **Data Diff** | Compare your data between any two points in time |
| 🔗 **SHA-256 Hash Chain** | Cryptographic tamper-proof audit trail |
| 📋 **SOC 2 Reports** | Generate compliance evidence in one click |
| 📝 **Change Log** | Full before/after history for every row |
| 🌑 **Dark Dashboard** | Beautiful UI — no config needed |

---

## 🚀 Quick Start

### PostgreSQL (NeonDB, Supabase, Railway, self-hosted)

```bash
# Install
pip install git+https://github.com/zarrarerror/shayntech-timetravel.git

# Initialize tracking on your database
timetravel init-pg "postgresql://user:pass@host/dbname"

# Launch the dashboard
timetravel serve --pg "postgresql://user:pass@host/dbname"
```

Open **http://localhost:8765** — your time machine is ready.

### SQLite

```bash
# Initialize tracking
timetravel init mydatabase.db

# Launch the dashboard
timetravel serve mydatabase.db
```

### Docker

```bash
# Clone the repo
git clone https://github.com/zarrarerror/shayntech-timetravel.git
cd shayntech-timetravel

# Set your connection string and start
TT_PG_CONN="postgresql://user:pass@host/dbname" docker-compose up
```

---

## 🎯 The Problem It Solves

Most databases only tell you what data looks like *right now*. When something goes wrong — a bad migration, an accidental DELETE, a rogue script — you're left digging through backups or begging your cloud provider.

TimeTravel makes your database **self-auditing from day one**:

- Direct psql edits? **Captured.**
- App-level deletes? **Captured.**
- Need it back? **One click.**

---

## 📖 CLI Reference

```bash
# PostgreSQL
timetravel init-pg "postgresql://..."          # baseline + install triggers
timetravel serve --pg "postgresql://..."       # launch dashboard
timetravel serve --pg "..." --exclude session  # exclude noisy tables

# SQLite
timetravel init mydb.db                        # start tracking
timetravel serve mydb.db                       # launch dashboard

# Query & reports (works for both)
timetravel query --at "2025-01-01" --table orders
timetravel log --table orders --row 42
timetravel verify mydb.db
timetravel report --type all
```

---

## 🔧 Dashboard Pages

| Page | What it shows |
|---|---|
| **Overview** | Tables tracked, total changes, chain integrity, recent activity |
| **Time Travel Query** | Your data as it was at any timestamp |
| **Live Feed** | Real-time stream of every change |
| **Diff** | Side-by-side comparison between two dates |
| **Change Log** | Full INSERT/UPDATE/DELETE history with Restore button |
| **Chain Verify** | Cryptographic verification — API entries + auto-captured |
| **SOC 2 Reports** | Integrity, Audit Trail, and Retention reports |

---

## 🛡️ Security & Privacy

- Runs on **your infrastructure** — data never leaves your server
- **Open source** — fully auditable, no black boxes
- **No telemetry** — no phone-home, no analytics
- **MIT license** — free to use, modify, distribute

---

## 🔧 Requirements

- Python 3.10+
- PostgreSQL **or** SQLite
- `fastapi` + `uvicorn` (for dashboard)
- `psycopg2-binary` (for PostgreSQL)

```bash
pip install fastapi uvicorn psycopg2-binary
```

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

<p align="center">
  Built by <a href="https://shayntech.com">Shayntech</a><br>
  <a href="https://github.com/zarrarerror/shayntech-timetravel">⭐ Star on GitHub</a> if this saved your data
</p>
