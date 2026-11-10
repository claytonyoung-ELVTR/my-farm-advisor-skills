#!/usr/bin/env bash
# Copy this subskill into the data-pipeline runtime so it can run against the
# generated grower data without the repo checkout.
#
# The runtime path (${DATA_PIPELINE_DATA_ROOT}/data-pipeline/skills/<skill>) is
# deliberately outside the runtime src/ tree, because install.sh replaces src/
# on refresh. Nothing here touches generated grower data.

set -euo pipefail

SKILL_DIR=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
SKILL_NAME="grower-webmap"

DATA_ROOT="${DATA_PIPELINE_DATA_ROOT:-}"
if [[ -z "${DATA_ROOT}" ]]; then
  printf 'error: DATA_PIPELINE_DATA_ROOT is required\n' >&2
  exit 2
fi
if [[ ! -d "${DATA_ROOT}" ]]; then
  printf 'error: runtime data root does not exist: %s\n' "${DATA_ROOT}" >&2
  exit 2
fi

RUNTIME_BASE="${DATA_ROOT}/data-pipeline"
if [[ ! -d "${RUNTIME_BASE}" ]]; then
  printf 'error: runtime base missing: %s\n' "${RUNTIME_BASE}" >&2
  exit 2
fi

DEST="${RUNTIME_BASE}/skills/${SKILL_NAME}"
mkdir -p "${DEST}"

# Copy without following the checkout's untracked artifacts.
(
  cd "${SKILL_DIR}"
  tar \
    --exclude='__pycache__' --exclude='*/__pycache__' \
    --exclude='.pytest_cache' --exclude='*/.pytest_cache' \
    -cf - .
) | (
  cd "${DEST}"
  tar -xf -
)

printf 'installed %s -> %s\n' "${SKILL_NAME}" "${DEST}"
printf 'render with:\n'
printf '  %s/data-pipeline/.venv/bin/python %s/scripts/render_growers.py --data-root %s\n' \
  "${DATA_ROOT}" "${DEST}" "${DATA_ROOT}"
