#!/usr/bin/env bash
#SBATCH --job-name=lab2-heat
#SBATCH --partition=compute
set -Eeuo pipefail
: "${LAB_PROJECT_DIR:?}" "${LAB_MESH:?}" "${LAB_RUN_DIR:?}" "${LAB_STEPS:?}" "${LAB_MODE:?}"
mkdir -p "$LAB_RUN_DIR"
start=$(date +%s%N)
debug_args=()
[[ "${LAB_DEBUG:-0}" == 1 ]] && debug_args+=(--debug)
# OpenMPI supplied by this cluster is not built with Slurm PMI support, so
# launching Python directly with srun fails in MPI_Init.  mpirun still uses
# the hosts allocated by Slurm and works with this OpenMPI build.
# eth0 is Vagrant NAT and is not routable between workers; eth1 is the
# 192.168.56.0/24 cluster network used by Slurm and NFS.
launcher=(mpirun --bind-to none --mca oob_tcp_if_include eth1 --mca btl_tcp_if_include eth1 -np "$SLURM_NTASKS")
if [[ "$LAB_MODE" =~ ^(simulation|all)$ ]]; then
  "${launcher[@]}" python3 "$LAB_PROJECT_DIR/src/heat_mpi.py" --mesh "$LAB_MESH" --output-dir "$LAB_RUN_DIR" --steps "$LAB_STEPS" --initial-temperature "$LAB_INITIAL_TEMPERATURE" --hot-temperature "$LAB_HOT_TEMPERATURE" --source-radius "$LAB_SOURCE_RADIUS" --save-every "$LAB_SAVE_EVERY" --conductivity "$LAB_CONDUCTIVITY" --rho "$LAB_RHO" --specific-heat "$LAB_SPECIFIC_HEAT" --thickness "$LAB_THICKNESS" "${debug_args[@]}"
else
  "${launcher[@]}" python3 "$LAB_PROJECT_DIR/src/profile_tasks.py" --mode "$LAB_MODE" --mesh "$LAB_MESH" --output-dir "$LAB_RUN_DIR" --conductivity "$LAB_CONDUCTIVITY"
fi
end=$(date +%s%N)
awk -v a="$start" -v b="$end" 'BEGIN { printf "elapsed_seconds\n%.9f\n", (b-a)/1000000000 }' > "$LAB_RUN_DIR/job_elapsed.csv"
