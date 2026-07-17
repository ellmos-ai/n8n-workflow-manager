FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    N8N_MANAGER_CONFIG_DIR=/config \
    N8N_MANAGER_DATA_DIR=/data \
    N8N_MANAGER_ALLOW_REMOTE=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY n8nManager/ ./n8nManager/
RUN python -m pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 manager \
    && mkdir -p /config /data \
    && chown -R manager:manager /config /data

USER manager
VOLUME ["/config", "/data"]
EXPOSE 8100
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8100/api/status', timeout=3)"

CMD ["n8n-manager", "serve", "--host", "0.0.0.0", "--port", "8100"]
