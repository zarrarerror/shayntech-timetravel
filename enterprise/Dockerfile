FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY enterprise/pyproject.toml .
RUN pip install --no-cache-dir fastapi uvicorn jinja2 python-multipart

# Install the base package
COPY . /app/
RUN pip install -e .

EXPOSE 8080

ENV TT_DATA_DIR=/data
VOLUME /data

CMD ["python", "-m", "enterprise.server"]
