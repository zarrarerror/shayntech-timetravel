FROM python:3.11-slim

LABEL maintainer="Shayntech <hello@shayntech.com>"
LABEL description="Shayntech TimeTravel — Database time travel & SOC 2 compliance dashboard"

WORKDIR /app

# Install psycopg2 system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir fastapi uvicorn psycopg2-binary

# Copy source
COPY src/ /app/src/
COPY pyproject.toml /app/

# Install the package
RUN pip install --no-cache-dir -e .

# Data volume for SQLite mode
VOLUME /data

EXPOSE 8080

# Environment variables
# TT_PG_CONN        — PostgreSQL connection string (optional, uses SQLite if not set)
# TT_DB_PATH        — SQLite database path (default: /data/timetravel.db)
# TT_HOST           — bind host (default: 0.0.0.0)
# TT_PORT           — port (default: 8080)
# TT_EXCLUDE_TABLES — comma-separated tables to skip tracking (e.g. session,logs,cache)

CMD ["python", "-c", "\
import os, sys; \
sys.path.insert(0, '/app/src'); \
from shayntech_timetravel.server import serve; \
excl = [t.strip() for t in os.environ.get('TT_EXCLUDE_TABLES','').split(',') if t.strip()]; \
serve( \
  db_path=os.environ.get('TT_DB_PATH', '/data/timetravel.db') if not os.environ.get('TT_PG_CONN') else None, \
  pg_conn_str=os.environ.get('TT_PG_CONN'), \
  host=os.environ.get('TT_HOST', '0.0.0.0'), \
  port=int(os.environ.get('TT_PORT', '8080')), \
  open_browser=False, \
  exclude_tables=excl or None \
)"]
