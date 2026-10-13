#!/usr/bin/env bash
set -euo pipefail

VERSION="1.7.12"
ARCHIVE="actionlint_${VERSION}_linux_amd64.tar.gz"
EXPECTED_SHA256="8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8"
CACHE_DIR="${TMPDIR:-/tmp}/georisk-actionlint-${VERSION}"
mkdir -p "${CACHE_DIR}"

if [[ ! -x "${CACHE_DIR}/actionlint" ]]; then
  curl --fail --silent --show-error --location \
    "https://github.com/rhysd/actionlint/releases/download/v${VERSION}/${ARCHIVE}" \
    --output "${CACHE_DIR}/${ARCHIVE}"
  printf '%s  %s\n' "${EXPECTED_SHA256}" "${CACHE_DIR}/${ARCHIVE}" | sha256sum --check --status
  tar -xzf "${CACHE_DIR}/${ARCHIVE}" -C "${CACHE_DIR}" actionlint
fi

"${CACHE_DIR}/actionlint" -shellcheck= -pyflakes= .github/workflows/*.yml
