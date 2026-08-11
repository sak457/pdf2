# syntax=docker/dockerfile:1
#
# Interactive AML Intelligence dashboard (Streamlit) — amd64.
#
# Unlike the batch PDF generator, this image needs NO system Chromium: kaleido
# 0.2.1 bundles its own engine for static chart export, so the image is slim.
#
#   Build : docker buildx build --platform linux/amd64 -f Dockerfile.app -t aml-dashboard:1.0 --load .
#
#   Run (persist the SQLite database on a named volume, set real admin creds):
#     docker volume create aml-data
#     docker run --rm -p 8501:8501 \
#         -v aml-data:/data \
#         -e AML_ADMIN_USERS=admin \
#         -e AML_ADMIN_PASSWORD='change-me-please' \
#         aml-dashboard:1.0
#   Open  : http://localhost:8501   (log in as the admin user above)
#
# Auth / storage environment variables (see README):
#   AML_ADMIN_USERS     comma-separated admin usernames        (default: admin)
#   AML_ADMIN_PASSWORD  password for the bootstrapped admin(s)  (default: admin —
#                       the app shows a "change me" warning until you set this)
#   AML_DB_PATH         SQLite file path; keep it on a volume   (default below)

FROM --platform=linux/amd64 python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHERUSAGESTATS=false \
    AML_DB_PATH=/data/aml.db \
    AML_ADMIN_USERS=admin
    # AML_ADMIN_PASSWORD is intentionally NOT baked in — supply it at `docker run`
    # so the default-password warning clears and a real credential is used.

WORKDIR /app

# Fonts so emoji / symbols in the UI and exported PDF render correctly.
RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-noto-color-emoji fonts-dejavu-core fontconfig ca-certificates \
    && fc-cache -f && rm -rf /var/lib/apt/lists/*

COPY requirements-app.txt .
RUN pip install -r requirements-app.txt

COPY app/ ./app/
COPY .streamlit/ ./.streamlit/

# Durable storage for the SQLite database (users + saved work sessions).
# Mount a named volume or host path here so data survives container restarts.
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

ENTRYPOINT ["streamlit", "run", "app/app.py", \
            "--server.port=8501", "--server.address=0.0.0.0"]
