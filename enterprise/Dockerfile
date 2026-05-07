FROM python:3.11-slim

WORKDIR /app

# Install system deps for weasyprint + psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 libffi-dev libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    fastapi uvicorn jinja2 python-multipart \
    psycopg2-binary weasyprint

# Copy and install the base package
COPY . /app/
RUN pip install -e .

EXPOSE 8080

ENV TT_DATA_DIR=/data
ENV TT_REPORT_DIR=/data/reports
VOLUME /data

CMD ["python", "-m", "enterprise.server"]
