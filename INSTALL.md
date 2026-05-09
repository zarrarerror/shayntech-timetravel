# Shayntech TimeTravel — Complete Installation Guide

> **For clients installing on-premises.** Covers fresh server from zero to running dashboard in Docker.

---

## What You Will Have at the End

- TimeTravel dashboard running at `http://YOUR-SERVER-IP:8080`
- Connected to your PostgreSQL or SQLite database
- Real-time change tracking, time travel queries, SOC 2 reports

---

## Requirements

| Item | Minimum |
|------|---------|
| OS | Ubuntu 20.04 / 22.04 / 24.04 (or any Linux with Docker) |
| RAM | 512 MB |
| Disk | 2 GB |
| CPU | 1 core |
| Network | Outbound internet (to pull Docker image) |
| Database | PostgreSQL (any version) or SQLite file |

---

## OPTION A — Docker (Recommended for Clients)

Docker is the easiest way. Install it once, run anywhere.

---

### Step 1 — Install Docker

**Ubuntu / Debian:**
```bash
# Remove old versions if any
sudo apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null

# Install prerequisites
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine + Compose
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Allow current user to run Docker without sudo
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version
docker compose version
```

**Windows (Docker Desktop):**
1. Download from: https://www.docker.com/products/docker-desktop/
2. Run installer → Restart PC
3. Open Docker Desktop → wait for it to say "Engine running"
4. Open PowerShell and run: `docker --version`

**macOS:**
```bash
brew install --cask docker
# Then open Docker Desktop from Applications
```

---

### Step 2 — Get the TimeTravel Code

```bash
# Clone the repository
git clone https://github.com/zarrarerror/shayntech-timetravel.git
cd shayntech-timetravel
```

Or if you received a ZIP file:
```bash
unzip shayntech-timetravel.zip
cd shayntech-timetravel
```

---

### Step 3 — Build the Docker Image

```bash
docker build -t shayntech-timetravel:latest .
```

This takes about 2–3 minutes the first time (downloads Python, installs packages).

---

### Step 4A — Run with PostgreSQL (NeonDB / Supabase / RDS / any Postgres)

```bash
docker run -d \
  --name shayntech-timetravel \
  --restart unless-stopped \
  -p 8080:8080 \
  -e TT_PG_CONN="postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require" \
  shayntech-timetravel:latest
```

Replace `postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require` with your actual connection string.

**Example with NeonDB:**
```bash
docker run -d \
  --name shayntech-timetravel \
  --restart unless-stopped \
  -p 8080:8080 \
  -e TT_PG_CONN="postgresql://neondb_owner:YOUR_PASSWORD@ep-xxxx.neon.tech/neondb?sslmode=require" \
  shayntech-timetravel:latest
```

---

### Step 4B — Run with SQLite (local database file)

```bash
docker run -d \
  --name shayntech-timetravel \
  --restart unless-stopped \
  -p 8080:8080 \
  -v /absolute/path/to/your/database.db:/data/timetravel.db \
  shayntech-timetravel:latest
```

Replace `/absolute/path/to/your/database.db` with the full path to your `.db` file.

---

### Step 4C — Run with Docker Compose (easiest long-term)

Create a `.env` file next to `docker-compose.yml`:

```bash
# .env file
TT_PG_CONN=postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require
```

Then run:
```bash
docker compose up -d
```

To update in the future:
```bash
git pull
docker compose down
docker build -t shayntech-timetravel:latest .
docker compose up -d
```

---

### Step 5 — Open the Dashboard

Open your browser and go to:

```
http://localhost:8080
```

If on a remote server, replace `localhost` with the server's IP address:
```
http://YOUR-SERVER-IP:8080
```

---

### Step 6 — Initialize Tracking (First Time Only)

The first time you connect, run the init command to baseline your existing data:

```bash
# For PostgreSQL
docker exec shayntech-timetravel python -m shayntech_timetravel.cli init \
  --pg "postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"

# For SQLite
docker exec shayntech-timetravel python -m shayntech_timetravel.cli init \
  /data/timetravel.db
```

---

### Management Commands

```bash
# View logs
docker logs -f shayntech-timetravel

# Stop the dashboard
docker stop shayntech-timetravel

# Start again
docker start shayntech-timetravel

# Restart
docker restart shayntech-timetravel

# Remove container (does NOT delete your database)
docker rm -f shayntech-timetravel

# Check status
docker ps | grep timetravel
```

---

## OPTION B — Run Without Docker (Python Direct)

Use this if Docker is not available or for development.

---

### Step 1 — Install Python 3.11+

**Ubuntu:**
```bash
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3.11-pip
```

**Or use uv (faster, no sudo needed):**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
```

---

### Step 2 — Get the Code

```bash
git clone https://github.com/zarrarerror/shayntech-timetravel.git
cd shayntech-timetravel
```

---

### Step 3 — Create Virtual Environment & Install

**With uv (recommended):**
```bash
uv venv .venv
uv pip install fastapi uvicorn psycopg2-binary -p .venv
uv pip install -e . -p .venv
```

**With standard pip:**
```bash
python3 -m venv .venv
source .venv/bin/activate          # Linux/Mac
# .venv\Scripts\activate           # Windows PowerShell

pip install fastapi uvicorn psycopg2-binary
pip install -e .
```

---

### Step 4 — Run the Dashboard

**PostgreSQL:**
```bash
.venv/bin/python -m shayntech_timetravel.cli serve \
  --pg "postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require" \
  --host 0.0.0.0 \
  --port 8080
```

**SQLite:**
```bash
.venv/bin/python -m shayntech_timetravel.cli serve /path/to/database.db \
  --host 0.0.0.0 \
  --port 8080
```

**Run in background (Linux):**
```bash
nohup .venv/bin/python -m shayntech_timetravel.cli serve \
  --pg "postgresql://USER:..." \
  --host 0.0.0.0 --port 8080 --no-browser \
  > /var/log/timetravel.log 2>&1 &

echo "Running as PID $!"
```

---

### Step 5 — Keep It Running with systemd (Linux Server)

Create a service file so it auto-starts on reboot:

```bash
sudo nano /etc/systemd/system/timetravel.service
```

Paste this (replace paths and connection string):
```ini
[Unit]
Description=Shayntech TimeTravel Dashboard
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/shayntech-timetravel
Environment="TT_PG=postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"
ExecStart=/home/YOUR_USERNAME/shayntech-timetravel/.venv/bin/python \
  -m shayntech_timetravel.cli serve \
  --pg ${TT_PG} \
  --host 0.0.0.0 \
  --port 8080 \
  --no-browser
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable timetravel
sudo systemctl start timetravel
sudo systemctl status timetravel
```

---

## Firewall (if on a remote server)

If clients access from outside, open port 8080:

```bash
# Ubuntu UFW
sudo ufw allow 8080/tcp
sudo ufw reload

# CentOS/RHEL firewalld
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload
```

---

## Reverse Proxy (Optional — for domain name + HTTPS)

To serve at `https://timetravel.yourdomain.com`:

```bash
sudo apt-get install -y nginx
```

Create `/etc/nginx/sites-available/timetravel`:
```nginx
server {
    listen 80;
    server_name timetravel.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/timetravel /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Add free HTTPS with Let's Encrypt
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d timetravel.yourdomain.com
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `docker: command not found` | Run Step 1 (Install Docker) again |
| `port 8080 already in use` | Run `sudo fuser -k 8080/tcp` then retry |
| `connection refused` on remote server | Open firewall: `sudo ufw allow 8080/tcp` |
| `ModuleNotFoundError: psycopg2` | Run `pip install psycopg2-binary` |
| Dashboard loads but no tables | Run `init` command (Step 6) |
| NeonDB SSL error | Ensure connection string ends with `?sslmode=require` |
| `permission denied` on Docker | Run `sudo usermod -aG docker $USER` then log out and back in |

---

## Environment Variable Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `TT_PG_CONN` | PostgreSQL connection string | `postgresql://user:pass@host/db?sslmode=require` |
| `TT_DB_PATH` | SQLite database file path (when not using PG) | `/data/mydb.db` |
| `TT_HOST` | Host to bind | `0.0.0.0` |
| `TT_PORT` | Port to listen on | `8080` |

---

## Quick Reference Card

```bash
# ── Install Docker (Ubuntu, one time) ────────────────────────────
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker

# ── Get the code ──────────────────────────────────────────────────
git clone https://github.com/zarrarerror/shayntech-timetravel.git
cd shayntech-timetravel

# ── Build ─────────────────────────────────────────────────────────
docker build -t shayntech-timetravel:latest .

# ── Run (PostgreSQL) ──────────────────────────────────────────────
docker run -d --name timetravel --restart unless-stopped \
  -p 8080:8080 \
  -e TT_PG_CONN="postgresql://user:pass@host/db?sslmode=require" \
  shayntech-timetravel:latest

# ── Open ──────────────────────────────────────────────────────────
# Browser → http://localhost:8080

# ── Logs ──────────────────────────────────────────────────────────
docker logs -f timetravel

# ── Stop ──────────────────────────────────────────────────────────
docker stop timetravel
```

---

*Shayntech TimeTravel — Open Source | MIT License*
*Support: hello@shayntech.com*
