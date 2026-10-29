#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"; source "$SCRIPT_DIR/lib.bash"
repetitions=3; steps=$STEPS; nodes='1 2 3 4'; modes='load adjacency partition simulation'
while (( $# )); do case "$1" in --repetitions) repetitions=${2:?}; shift 2;; --steps) steps=${2:?}; shift 2;; --nodes) nodes=${2:?}; shift 2;; --modes) modes=${2:?}; shift 2;; --mesh) MESH_PATH=${2:?}; shift 2;; *) die "Usage: $0 [--modes 'load adjacency partition simulation'] [--mesh PATH] [--repetitions N] [--steps N] [--nodes '1 2 3 4']";; esac; done
[[ -r "$MESH_PATH" ]] || die "Mesh not found: $MESH_PATH"
for ((repeat=1; repeat<=repetitions; repeat++)); do
  for mode in $modes; do for count in $nodes; do "$SCRIPT_DIR/run_experiment.bash" --mode "$mode" --mesh "$MESH_PATH" --nodes "$count" --repeat "$repeat" --steps "$steps" --tag benchmark; done; done
done
