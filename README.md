# 🔮 Shayntech TimeTravel

> **Git for your database. SOC 2 evidence built in.**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)

Timetravel adds **time travel queries** and **SOC 2 technical evidence** to any SQLite database. Every change is tracked in an immutable hash chain — like GitHub, but for your data.

```bash
# Install from GitHub
pip install git+https://github.com/zarrarerror/shayntech-timetravel.git

# Or clone and run
git clone https://github.com/zarrarerror/shayntech-timetravel.git
cd shayntech-timetravel
pip install -e .

# Run a complete demo
timetravel demo

# Or use with your own database
timetravel init mydatabase.db
timetravel query --at "2025-01-01" --table users
timetravel report --type all
```

**⚠️ What this is:** A tool that generates **technical evidence** for SOC 2 audits (hash chains, change logs, integrity proofs). This evidence is what SOC 2 auditors review during certification.

**❌ What this is NOT:** A SOC 2 certification service. You still need a licensed third-party auditor to issue the actual SOC 2 certificate.

---

## ✨ Features

- 🕰️ **Time Travel Queries** — Query data as of any point in time
- 🔗 **Immutable Hash Chain** — SHA-256 linked chain, tamper-evident
- 📋 **SOC 2 Evidence Reports** — Integrity, Change Audit, Retention
- 🔍 **Data Diff** — See what changed between two dates
- 📝 **Row History** — Full change log for any row
- ✅ **Chain Verification** — Instantly detect tampering
- 💻 **CLI Tool** — Works with any SQLite database

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
open ./reports/soc2-integrity-report.html
```

---

## 📖 CLI Commands

| Command | Description |
|---------|-------------|
| `timetravel init <db>` | Start tracking an existing database |
| `timetravel query --at <time> --table <t>` | Query data as of a point in time |
| `timetravel diff --from <t> --to <t> --table <t>` | Show differences between two dates |
| `timetravel log --table <t> [--row <id>]` | Show change history for a row |
| `timetravel verify <db>` | Verify hash chain integrity |
| `timetravel report --type <type>` | Generate SOC 2 evidence reports |
| `timetravel demo` | Run interactive demo with sample data |

---

## 🏗️ Architecture

```
Your App → [TimeTravel Core] ──→ Your Database
                  │
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

- **Runs on YOUR infrastructure** — your data never leaves your server
- **Open source** — fully auditable, no black boxes
- **No telemetry** — no phone-home, no analytics
- **MIT license** — free to use, modify, distribute

---

## 🔧 Requirements

- Python 3.10+
- SQLite

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

<p align="center">
  Built by <a href="https://shayntech.com">Shayntech</a> — AI consulting and software.<br>
  Also check out our <a href="https://shayntech.com/products/excel-ai">free Excel AI Agent</a>
</p>
