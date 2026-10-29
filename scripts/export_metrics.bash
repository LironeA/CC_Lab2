#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"; source "$SCRIPT_DIR/lib.bash"
archive="$RESULTS_ROOT/metrics_bundle.tar.gz"
# Final NPZ fields are useful for visualization but are not needed for the
# benchmark analysis and may still be momentarily locked by NFS. Export only
# reproducible CSV metrics and per-rank CSV timings, as in Lab1.
mapfile -t csv_files < <(cd "$RESULTS_ROOT" && find raw -type f \( -path '*/worker/*.csv' -o -name summary.csv \) -print)
tar -czf "$archive" -C "$RESULTS_ROOT" metrics "${csv_files[@]}"
echo "$archive"
