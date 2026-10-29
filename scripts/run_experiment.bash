#!/usr/bin/env bash
# Submit one MPI run and append only its measured metadata to runs.csv.
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"; source "$SCRIPT_DIR/lib.bash"
nodes= mode=simulation repeat=1 tag=manual steps=$STEPS mesh=$MESH_PATH source_radius=$HOT_SOURCE_RADIUS save_every=0
while (( $# )); do case "$1" in
  --nodes) nodes=${2:?}; shift 2;; --mode) mode=${2:?}; shift 2;; --repeat) repeat=${2:?}; shift 2;; --tag) tag=${2:?}; shift 2;;
  --steps) steps=${2:?}; shift 2;; --mesh) mesh=${2:?}; shift 2;; --source-radius) source_radius=${2:?}; shift 2;; --save-every) save_every=${2:?}; shift 2;; *) die "Usage: $0 --nodes N [--mode load|adjacency|partition|simulation|all] [--repeat R] [--steps N] [--mesh PATH] [--source-radius R] [--save-every N] [--tag NAME]";; esac; done
[[ "$nodes" =~ ^[1-9][0-9]*$ && "$repeat" =~ ^[0-9]+$ && "$steps" =~ ^[1-9][0-9]*$ && "$mode" =~ ^(load|adjacency|partition|simulation|all)$ && -r "$mesh" ]] || die "Invalid arguments or unreadable mesh"
ready=$(sinfo -h -N -p "$PARTITION" -t idle -o '%N' | wc -l)
(( ready >= nodes )) || die "Need $nodes idle workers; found $ready"
run_id="${tag}_n${nodes}_r${repeat}_$(date +%Y%m%dT%H%M%S)_$RANDOM"; run_dir="$RESULTS_ROOT/raw/$run_id"; mkdir -p "$run_dir"
jobid=$(sbatch --parsable --chdir=/tmp --partition="$PARTITION" --nodes="$nodes" --ntasks="$nodes" --ntasks-per-node=1 --cpus-per-task=1 --time="$SLURM_TIME_LIMIT" \
  --export="ALL,LAB_MODE=$mode,LAB_PROJECT_DIR=$PROJECT_DIR,LAB_MESH=$mesh,LAB_RUN_DIR=$run_dir,LAB_STEPS=$steps,LAB_SOURCE_RADIUS=$source_radius,LAB_SAVE_EVERY=$save_every,LAB_INITIAL_TEMPERATURE=$INITIAL_TEMPERATURE,LAB_HOT_TEMPERATURE=$HOT_TEMPERATURE,LAB_CONDUCTIVITY=$CONDUCTIVITY,LAB_RHO=$RHO,LAB_SPECIFIC_HEAT=$SPECIFIC_HEAT,LAB_THICKNESS=$THICKNESS" \
  "$PROJECT_DIR/slurm/heat_solver.sbatch")
jobid=${jobid%%;*}; echo "Submitted $jobid: $run_id"
while squeue -h -j "$jobid" | grep -q .; do sleep 1; done
state=$(scontrol show job -o "$jobid" 2>/dev/null | sed -n 's/.*JobState=\([^ ]*\).*/\1/p'); state=${state:-UNKNOWN}
elapsed=$(tail -n1 "$run_dir/job_elapsed.csv" 2>/dev/null || true)
faces=$(tail -n1 "$run_dir/summary.csv" 2>/dev/null | cut -d, -f1); faces=${faces:-0}
metrics="$RESULTS_ROOT/metrics/runs.csv"
[[ -f "$metrics" ]] || echo 'run_id,job_id,status,mode,nodes,repeat,steps,faces,elapsed_seconds,run_dir' > "$metrics"
printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' "$run_id" "$jobid" "$state" "$mode" "$nodes" "$repeat" "$steps" "$faces" "$elapsed" "$run_dir" >> "$metrics"
[[ "$state" == COMPLETED && -f "$run_dir/summary.csv" ]] || die "Run failed or incomplete: $run_id ($state)"
echo "$run_id"
