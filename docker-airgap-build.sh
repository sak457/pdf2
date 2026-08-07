#!/usr/bin/env bash
#
# Build the AML report image for amd64 and export it as a portable tarball for
# an air-gapped deployment.
#
# Run this on a NETWORK-CONNECTED build host. It produces:
#     aml-report_<tag>_amd64.tar.gz
# Copy that single file into the air-gapped network, then on a server there:
#     gunzip -c aml-report_<tag>_amd64.tar.gz | docker load
#     mkdir -p output
#     docker run --rm -v "$PWD/output:/app/output" aml-report:<tag>
#
# Usage:  ./docker-airgap-build.sh [tag]      (tag defaults to "1.0")
set -euo pipefail

TAG="${1:-1.0}"
IMAGE="aml-report:${TAG}"
OUT="aml-report_${TAG}_amd64.tar.gz"
PLATFORM="linux/amd64"

echo ">> Building ${IMAGE} for ${PLATFORM} ..."
if docker buildx version >/dev/null 2>&1; then
  docker buildx build --platform "${PLATFORM}" -t "${IMAGE}" --load .
else
  # Fallback for older Docker without buildx (needs a native/emulated amd64 host)
  DOCKER_DEFAULT_PLATFORM="${PLATFORM}" docker build -t "${IMAGE}" .
fi

echo ">> Verifying image architecture ..."
ARCH="$(docker image inspect "${IMAGE}" --format '{{.Architecture}}')"
echo "   image architecture = ${ARCH}"
if [ "${ARCH}" != "amd64" ]; then
  echo "!! WARNING: image is '${ARCH}', not amd64 — check your buildx setup." >&2
fi

echo ">> Exporting to ${OUT} ..."
docker save "${IMAGE}" | gzip > "${OUT}"

echo ">> Done."
ls -lh "${OUT}"
cat <<EOF

Transfer ${OUT} into the air-gapped network, then on a target server:

    gunzip -c ${OUT} | docker load
    mkdir -p output
    # demo report from synthetic data:
    docker run --rm -v "\$PWD/output:/app/output" ${IMAGE}
    # or from a real statement:
    docker run --rm -v "\$PWD/output:/app/output" -v "\$PWD/in:/data:ro" \\
        ${IMAGE} --excel /data/statement.xlsx

Result: output/AML_Intelligence_Report.pdf
EOF
