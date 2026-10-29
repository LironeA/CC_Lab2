#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"; source "$SCRIPT_DIR/lib.bash"
resolution=100
while (( $# )); do case "$1" in --resolution) resolution=${2:?}; shift 2;; *) die "Usage: $0 [--resolution N]";; esac; done
mkdirs
[[ -f "$MESH_PATH" ]] && { echo "Mesh already exists: $MESH_PATH"; exit 0; }
python3 "$PROJECT_DIR/src/generate_grid.py" --output "$MESH_PATH" --resolution "$resolution"
