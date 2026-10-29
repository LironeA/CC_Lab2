#!/usr/bin/env python3
"""Measure one Lab2 pipeline stage independently under the same MPI allocation."""
from __future__ import annotations
import argparse, csv, socket, time
from pathlib import Path
import numpy as np
from mpi4py import MPI
from stl import mesh as stl_mesh
from heat_mpi import face_geometry, build_edges, spatial_partition

parser = argparse.ArgumentParser()
parser.add_argument("--mode", choices=("load", "adjacency", "partition"), required=True)
parser.add_argument("--mesh", type=Path, required=True)
parser.add_argument("--output-dir", type=Path, required=True)
parser.add_argument("--conductivity", type=float, default=1.0)
args = parser.parse_args()
comm = MPI.COMM_WORLD; rank, ranks = comm.rank, comm.size

if rank == 0:
    if args.mode == "load":
        start = time.perf_counter()
        triangles = np.asarray(stl_mesh.Mesh.from_file(str(args.mesh)).vectors, dtype=np.float64)
        centers, _ = face_geometry(triangles)
        payload = (len(triangles), 0)
    else:
        triangles = np.asarray(stl_mesh.Mesh.from_file(str(args.mesh)).vectors, dtype=np.float64)
        centers, _ = face_geometry(triangles)
        if args.mode == "adjacency":
            start = time.perf_counter()
            edge_i, edge_j, _ = build_edges(triangles, centers, args.conductivity)
            payload = (len(triangles), len(edge_i))
        else:
            edge_i, edge_j, _ = build_edges(triangles, centers, args.conductivity)
            start = time.perf_counter()
            owners = spatial_partition(centers, ranks)
            payload = (len(owners), len(edge_i))
else:
    start = None; payload = None
payload = comm.bcast(payload, root=0)
comm.Barrier(); elapsed = comm.bcast(time.perf_counter() - start if rank == 0 else None, root=0)
if rank == 0: args.output_dir.mkdir(parents=True, exist_ok=True)
comm.Barrier(); worker = args.output_dir / "worker"; worker.mkdir(exist_ok=True)
with (worker / f"rank-{rank}.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["hostname","rank","faces","ghost_faces","internal_edges","cross_edges","communication_seconds","compute_seconds","elapsed_seconds"])
    w.writerow([socket.gethostname(), rank, payload[0] if rank == 0 else 0, 0, payload[1] if rank == 0 else 0, 0, 0, elapsed if rank == 0 else 0, elapsed])
if rank == 0:
    (args.output_dir / "summary.csv").write_text(f"faces,edges,ranks,steps,dt,stability_dt,hot_face,final_energy,elapsed_seconds\n{payload[0]},{payload[1]},{ranks},0,,,,,,{elapsed}\n", encoding="utf-8")
    print(f"mode={args.mode} faces={payload[0]} elapsed={elapsed:.3f}s")
