FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PROFILES_ROOT=/data/profiles \
    LISTEN_ADDR=0.0.0.0:8080

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY static ./static

RUN pip install --no-cache-dir .

RUN useradd -r -u 10001 -m -d /home/chatapp chatapp \
 && mkdir -p /data/profiles \
 && chown -R chatapp:chatapp /data /app

USER chatapp
EXPOSE 8080
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8080/healthz').read()" || exit 1

CMD ["chatapp", "serve"]
