# syntax=docker/dockerfile:1
#
# Interactive AML Intelligence dashboard (Streamlit) — amd64.
#
# Unlike the batch PDF generator, this image needs NO system Chromium: kaleido
# 0.2.1 bundles its own engine for static chart export, so the image is slim.
#
#   Build : docker buildx build --platform linux/amd64 -f Dockerfile.app -t aml-dashboard:1.0 --load .
#   Run   : docker run --rm -p 8501:8501 aml-dashboard:1.0
#   Open  : http://localhost:8501

FROM --platform=linux/amd64 python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHERUSAGESTATS=false

WORKDIR /app

# Fonts so emoji / symbols in the UI and exported PDF render correctly.
RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-noto-color-emoji fonts-dejavu-core fontconfig ca-certificates \
    && fc-cache -f && rm -rf /var/lib/apt/lists/*

COPY requirements-app.txt .
RUN pip install -r requirements-app.txt

COPY app/ ./app/
COPY .streamlit/ ./.streamlit/

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

ENTRYPOINT ["streamlit", "run", "app/app.py", \
            "--server.port=8501", "--server.address=0.0.0.0"]
