# syntax=docker/dockerfile:1
#
# AML / Financial Intelligence report generator — air-gap-ready image.
#
# Targets x86_64 / amd64 servers (NOT arm). The platform is pinned so the image
# is amd64 even when the build host is arm (e.g. an Apple-silicon laptop building
# via QEMU). Build it once on a network-connected machine, export it with
# `docker save`, carry the tar into the air-gapped network, `docker load`, run.
#
# Everything the report needs at run time is baked in: Python deps, the Chromium
# browser, its shared libraries, and the fonts required to render the emoji and
# symbols used throughout the dashboard. No network access is needed to run.
#
#   Build : docker buildx build --platform linux/amd64 -t aml-report:1.0 --load .
#   Run   : docker run --rm -v "$PWD/output:/app/output" aml-report:1.0
#   Real  : docker run --rm -v "$PWD/output:/app/output" -v "$PWD/in:/data:ro" \
#                       aml-report:1.0 --excel /data/statement.xlsx

FROM --platform=linux/amd64 python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
    AML_INPUT_MODE=synthetic

WORKDIR /app

# --- Fonts for correct rendering of the emoji / symbols in the report --------
#   fonts-noto-color-emoji -> 💰 ⬇ ⬆ 🏦 ⚠ 👤 🏢 🚨 🕸 🎯 🟢 🟡 🔴 ... (colour emoji)
#   fonts-dejavu-core      -> matplotlib chart text + « » → – — … × · glyphs
# fontconfig + fc-cache make the fonts discoverable by Chromium & matplotlib.
RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-noto-color-emoji \
        fonts-dejavu-core \
        fontconfig \
        ca-certificates \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

# --- Python dependencies -----------------------------------------------------
COPY requirements.txt .
RUN pip install -r requirements.txt

# --- Chromium + its OS libraries, baked into the image -----------------------
# `--with-deps` also installs every shared library Chromium links against, so
# the finished image runs with zero external packages in the air-gapped env.
RUN playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# --- Application code ---------------------------------------------------------
COPY . .

# Reports are written here; mount a volume to collect the PDF/HTML/PNG.
RUN mkdir -p /app/output
VOLUME ["/app/output"]

# `docker run <img>`                    -> synthetic demo report
# `docker run <img> --excel /data/x.xlsx` -> report from a real statement
ENTRYPOINT ["python", "generate_report.py"]
CMD []
