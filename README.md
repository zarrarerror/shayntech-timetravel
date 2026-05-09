# ⏮ Shayntech TimeTravel

> **Accidentally deleted production data? Get it back. Git for your database — SOC 2 built in.**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![Works with PostgreSQL](https://img.shields.io/badge/PostgreSQL-supported-blue?logo=postgresql)](https://postgresql.org)
[![Works with NeonDB](https://img.shields.io/badge/NeonDB-supported-green)](https://neon.tech)

Shayntech TimeTravel tracks every INSERT, UPDATE, and DELETE in your database via an immutable SHA-256 hash chain. Query your data at any point in the past, compare changes between timestamps, verify tamper-evidence, and generate SOC 2 audit reports — all from the command line.

Works with **PostgreSQL** (NeonDB, Supabase, Railway, self-hosted) and **SQLite**.

---

## ✨ Features

- 🔮 **Time Travel Queries** — Reconstruct your database at any point in the past
- ↔️ **Data Diff** — Compare any two timestamps side by side
- 📝 **Row History** — Full change log for any table or row
- 🔗 **SHA-256 Hash Chain** — Tamper-evident, cryptographically linked entries
- ✅ **Chain Verification** — Instantly detect any unauthorized modification
- 📋 **SOC 2 Reports** — Generate audit-ready HTML evidence (Integrity, Audit Trail, Retention)
- 📡 **Auto-Capture Triggers** — PostgreSQL triggers track changes from any source, not just your app

---

## 🚀 Quick Start

```bash
# Install
pip install git+https://github.com/zarrarerror/shayntech-timetravel.git

# ── PostgreSQL ────────────────────────────────────────────────
# Initialize (baselines all tables + installs auto-capture triggers)
timetravel init --pg "postgresql://user:pass@host/dbname"

# Query data as of any point in time
timetravel query --pg "postgresql://..." --at "2025-01-01" --table orders

# ── SQLite ────────────────────────────────────────────────────
timetravel init mydb.db
timetravel query mydb.db --at "2025-06-01 12:00" --table users

# ── Try the demo ─────────────────────────────────────────────
timetravel demo
```

---

## 📖 CLI Reference

| Command | Description |
|---|---|
| `timetravel init <db>` | Initialize SQLite database for tracking |
| `timetravel init --pg <conn>` | Initialize PostgreSQL + install triggers |
| `timetravel query --at <time> --table <t>` | Query data at a point in time |
| `timetravel diff --from <t> --to <t> --table <t>` | Compare between two timestamps |
| `timetravel log --table <t> [--row <id>]` | Show change history |
| `timetravel verify [db]` | Verify SHA-256 hash chain integrity |
| `timetravel report --type <type>` | Generate SOC 2 evidence reports |
| `timetravel demo` | Run interactive demo with sample data |

### Options

```bash
# PostgreSQL with excluded tables (e.g. session, cache)
timetravel init --pg "postgresql://..." --exclude session,cache

# Report types
timetravel report --pg "postgresql://..." --type integrity --output ./reports
timetravel report --pg "postgresql://..." --type audit
timetravel report --pg "postgresql://..." --type retention
timetravel report --pg "postgresql://..." --type all
```

---

## 🔧 How It Works

```
Your App ──→ PostgreSQL / SQLite
               │
        [_tt_history table]
               │
    ┌──────────┴──────────┐
    │  SHA-256 Hash Chain  │
    │  Auto-capture Triggers│
    │  SOC 2 Reports       │
    └─────────────────────┘

Runs on YOUR infrastructure — data never leaves your server.
```

Every change is stored as a hash chain entry:
- Each entry contains a SHA-256 hash of itself + the previous entry's hash
- Any modification to past records is immediately detectable
- PostgreSQL triggers capture changes even from direct DB edits (psql, Neon console, etc.)

---

## 🛡️ Security & Privacy

- **Self-hosted** — your data never leaves your server
- **Open source** — fully auditable, no black boxes
- **No telemetry** — no phone-home, no analytics
- **MIT license** — free to use, modify, distribute

---

## 🔧 Requirements

- Python 3.10+
- PostgreSQL **or** SQLite
- `psycopg2-binary` for PostgreSQL mode

```bash
pip install psycopg2-binary  # PostgreSQL only
```

---

## 🏢 Enterprise Dashboard

Need a visual interface? The **Shayntech TimeTravel Enterprise Dashboard** includes:

- 🌑 Full web dashboard with dark UI
- 🔄 One-click row restore from the UI
- 📡 Live feed of all database changes
- 🐳 Docker deployment
- 📋 SOC 2 reports in the browser

👉 **Contact us:** [hello@shayntech.com](mailto:hello@shayntech.com)

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

<p align="center">
  Built by <a href="https://shayntech.com">Shayntech</a><br>
  <a href="https://github.com/zarrarerror/shayntech-timetravel">⭐ Star on GitHub</a> if this saved your data
</p>
