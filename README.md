# 🔮 Shayntech TimeTravel

> **Git for your database. SOC 2 evidence built in.**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)

Timetravel is an open-source tool that adds **time travel queries** and **SOC 2 compliance evidence** to any SQLite database. Every change is tracked in an immutable hash chain — like GitHub, but for your data.

```bash
pip install shayntech-timetravel
timetravel init mydb.db
timetravel query --at "2025-01-01" --table users
timetravel report --type all
```

---

## ✨ Features

### 🕰️ Time Travel Queries
Query your database as it existed at any point in time:
```sql
-- Current data
SELECT * FROM users → Alice: manager, Bob: editor, Charlie: viewer, Diana: editor

-- Data as of Jan 1, 2024
timetravel query --at "2024-01-01" --table users
→ Alice: admin, Bob: editor, Charlie: viewer
```

### 🔗 Immutable Hash Chain
Every change is hashed and linked to the previous change — tampering breaks the chain:
```
Entry #1: hash(●) → Entry #2: hash(●) → Entry #3: hash(●)
                                        ↑
                              Tampering detected here!
```

### 📋 SOC 2 Evidence Reports
Auto-generate auditor-ready reports:
- **Data Integrity Report** — Proves no data was tampered with
- **Change Audit Report** — Every change, by user, at what time
- **Retention Report** — Certifies data existed at a specific date

---

## 🚀 Quick Start

```bash
# Install
pip install shayntech-timetravel

# Run a complete demo
timetravel demo

# Or use with your own database
timetravel init mydatabase.db
timetravel query --at "2025-01-01" --table users
timetravel log --table orders --row 42
timetravel report --type all --output ./reports

# Open the reports in your browser
open ./reports/soc2-integrity-report.html
```

---

## 📖 Commands

| Command | Description |
|---------|-------------|
| `timetravel init <db>` | Start tracking an existing database |
| `timetravel query --at <time> --table <t>` | Query data as of a point in time |
| `timetravel diff --from <t> --to <t> --table <t>` | Show differences between two dates |
| `timetravel log --table <t> [--row <id>]` | Show change history |
| `timetravel verify <db>` | Verify hash chain integrity |
| `timetravel report --type <type>` | Generate SOC 2 evidence reports |
| `timetravel demo` | Run interactive demo with sample data |

---

## 🏗️ Architecture

```
Your App → [TimeTravel Proxy] → Your Database
                  ↓
         ┌────────┴────────┐
         │ Change Logger   │
         │ Hash Chain      │
         │ SOC 2 Reports   │
         └─────────────────┘
         Runs on YOUR infrastructure
         Your data never leaves your server
```

---

## 🛡️ Security & Privacy

- **Runs on your infrastructure** — your data never leaves your server
- **Open source** — fully auditable, no black boxes
- **No telemetry** — no phone-home, no analytics, no tracking
- **MIT license** — use it anywhere, modify it freely

---

## 🔧 Requirements

- Python 3.10+
- SQLite 3.x (built into Python)

---

## 🤝 Why Open Source?

Shayntech builds practical AI and data tools for real businesses. Our [Excel AI Agent](https://shayntech.com/products/excel-ai) is a free open-source AI co-pilot for Microsoft Excel. TimeTravel is the next step — because data integrity should be accessible to every company, not just ones with expensive auditors.

**We make money from:** Enterprise support, custom integrations, and SOC 2 consulting for companies that need hands-on help.

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

<p align="center">
  Built by <a href="https://shayntech.com">Shayntech</a> — AI consulting and software.
</p>
