# 🔮 Shayntech TimeTravel

> **Git for your database. SOC 2 evidence built in.**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)

Timetravel adds **time travel queries** and **SOC 2 technical evidence** to any database. Every change is tracked in an immutable hash chain — like GitHub, but for your data.

```bash
pip install shayntech-timetravel
timetravel init mydb.db
timetravel query --at "2025-01-01" --table users
timetravel report --type all
```

**⚠️ What this is:** A tool that generates **technical evidence** for SOC 2 audits (hash chains, change logs, integrity proofs). This evidence is what SOC 2 auditors review during certification.

**❌ What this is NOT:** A SOC 2 certification service. You still need a licensed third-party auditor (Schellman, A-LIGN, Prescient Assurance) to issue the actual SOC 2 certificate.

**Why it matters:** SOC 2 prep normally costs $20k-100k and takes weeks of manual evidence collection. This tool automates 80% of that — the evidence is ready before your auditor even looks. You save money and time.

---

## ✨ Features

| Tier | Features | Price |
|------|----------|-------|
| **Free** (Open Source) | Time travel queries, hash chain, CLI, HTML reports | $0 |
| **Enterprise** | Web dashboard, PDF reports, PostgreSQL/MySQL, Docker, SSO, SLA support | $99/mo |

### Free Edition (Open Source - MIT)
- 🕰️ **Time Travel Queries** — Query data as of any point in time
- 🔗 **Immutable Hash Chain** — SHA-256 linked chain, tamper-evident
- 📋 **SOC 2 Evidence HTML Reports** — Integrity, Change Audit, Retention
- 🔍 **Data Diff** — See what changed between two dates
- 📝 **Row History** — Full change log for any row
- ✅ **Chain Verification** — Instantly detect tampering
- 💻 **CLI Tool** — Works with any SQLite database

### Enterprise Edition
- 🌐 **Web Dashboard** — Modern dark-themed UI, no CLI needed
- 📄 **Professional PDF Reports** — Auditor-ready format, downloadable
- 🗄️ **PostgreSQL & MySQL Support** — Works with production databases
- 🐳 **Docker Deployment** — One-command setup
- 🔐 **User Authentication** — Team access control
- 📊 **Compliance Dashboard** — Real-time evidence status
- ⚡ **Priority Support SLA** — 2-hour response time
- 🎯 **Custom Integrations** — Connect to your existing stack

---

## 🚀 Quick Start (Free Edition)

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

## 📖 CLI Commands (Free Edition)

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

## 🌐 Enterprise Dashboard

The Enterprise edition provides a full web dashboard for managing time travel and SOC 2 evidence:

```bash
# Coming soon
docker run -p 8080:8080 shayntech/timetravel-enterprise
```

### Dashboard Features:
- **Overview Panel** — Real-time compliance status, change counts, chain health
- **Time Travel Browser** — Select any table, pick a date, see historical data
- **Change Log Viewer** — Search, filter, export change history
- **SOC 2 Report Center** — Generate and download professional PDF reports
- **Database Configuration** — Connect SQLite, PostgreSQL, or MySQL
- **Team Management** — Add users, set permissions

---

## 🏗️ Architecture

```
                    ┌─────────────────────────────┐
                    │   Enterprise Dashboard        │
                    │   (Web UI, optional)         │
                    └──────────┬──────────────────┘
                               │
Your App → [TimeTravel Core] ──┤──→ Your Database
                  │            │
         ┌────────┴────────┐   │
         │ Change Logger   │   │
         │ Hash Chain      │   │
         │ SOC 2 Reports   │   │
         └─────────────────┘   │
                               │
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

## 💰 How This Makes Money (For Us)

The Free Edition is open source and always will be. We earn revenue from:

| What | Price | Who Needs It |
|------|-------|-------------|
| **Enterprise Dashboard** | $99/mo | Companies that want a web UI |
| **Support SLA** | $199/mo | 2-hour response, setup help |
| **SOC 2 Consulting** | $2k-5k one-time | We help prep your evidence for auditors |
| **Custom Development** | $10k+ | Special integrations, custom databases |

---

## 🔧 Requirements

- Python 3.10+
- SQLite (free edition) / PostgreSQL or MySQL (enterprise edition)

---

## 📄 License

Free Edition: MIT License  
Enterprise Edition: Proprietary (subscription)

---

<p align="center">
  Built by <a href="https://shayntech.com">Shayntech</a> — AI consulting and software.<br>
  Also check out our <a href="https://shayntech.com/products/excel-ai">free Excel AI Agent</a>
</p>
